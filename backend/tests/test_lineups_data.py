"""The line-ups data of the frontend (frontend/scripts/build_lineups.py) against the event data of the match."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "frontend" / "data" / "lineups" / "kba-ngr.json").read_text(encoding="utf-8"))
EVENTS = json.loads((ROOT / "output" / "events.json").read_text(encoding="utf-8"))
PLAYERS = {p["id"]: p for p in DATA["players"]}


def test_substitutions_and_red_card_follow_the_events():
    for e in EVENTS:
        if e["type"] == "substitution":
            off, on = PLAYERS[e["player_id"]], PLAYERS[e["player_in_id"]]
            assert off["off"] == {"t": e["frame"], "minute": e["minute"], "reason": "sub", "by": e["player_in_id"]}
            assert on["replaced"] == e["player_id"] and on["on"][0] == e["frame"]
    red = next(e for e in EVENTS if e["type"] == "red_card")
    assert PLAYERS[red["player_id"]]["off"] == {"t": red["frame"], "minute": "53", "reason": "red"}


def test_goals_and_assists_are_the_four_goals():
    goals = [(m[1], pid) for pid, p in PLAYERS.items() for m in p["moments"] if m[2] == "goal"]
    assert sorted(goals) == [("24", "NGR-09"), ("39", "KBA-11"), ("68", "NGR-20"), ("82", "KBA-19")]
    assists = sorted((m[1], pid) for pid, p in PLAYERS.items() for m in p["moments"] if m[2] == "assist")
    assert assists == [("24", "NGR-08"), ("39", "KBA-10"), ("68", "NGR-18"), ("82", "KBA-17")]


def test_shots_and_passes_add_up_to_the_events():
    shots = sum(len(p["acts"].get("S", [])) for p in DATA["players"])
    assert shots == sum(1 for e in EVENTS if e["type"] == "shot")
    xg = sum(x for p in DATA["players"] for _, x in p["acts"].get("S", []))
    assert abs(xg - sum(e["xg"] for e in EVENTS if e["type"] == "shot")) < 0.01
    passes = sum(len(p["acts"].get("P", [])) + len(p["acts"].get("p", [])) for p in DATA["players"])
    assert passes == sum(1 for e in EVENTS if e["type"] in ("pass", "cross"))


def test_corners_taken_with_first_contact_and_outcome():
    taken = DATA["corners"]
    assert len([c for c in taken if c["team"] == "kba"]) == 7 and len([c for c in taken if c["team"] == "ngr"]) == 3
    awarded = [e for e in EVENTS if e["type"] == "corner"]
    assert len(awarded) == 11                               # one at 59' is never taken (substitution)
    for c in taken:
        assert c["side"] in ("left", "right") and c["outcome"]["kind"] in ("header", "shot", "cleared", "short", "goal")
        assert c["firstTouch"]["id"] is None or c["firstTouch"]["id"] in PLAYERS
        # stored as a corner from the left: the taker's flag is at u 0
        assert all(-2 <= p["u"] <= 70 and p["v"] <= 23.5 for p in c["attackers"] + c["defenders"])
    assert DATA["cup"] == {"cornerGoals": {"kba": 0, "ngr": 0}}


def test_corner_heights_come_from_the_player_profiles():
    profiles = json.loads((ROOT / "script" / "pre_match_context.json").read_text(encoding="utf-8"))["player_profiles"]
    for c in DATA["corners"]:
        for p in c["attackers"] + c["defenders"]:
            assert p["height"] == profiles[p["id"]]["height_cm"] / 100


def test_positions_are_team_relative():
    # goalkeepers stand near their own goal, on the left, in both halves
    for gk in ("KBA-01", "NGR-01"):
        xs = PLAYERS[gk]["xy"][0::2]
        assert sum(xs) / len(xs) < 20
