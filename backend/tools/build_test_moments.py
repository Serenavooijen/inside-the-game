"""
Builds test FactSheets for the agents from the generator output.

    cd backend
    uv run python tools/build_test_moments.py [../output] [../script/match_script.json]

Writes ../fixtures/moments/<moment_id>.json. Every fact is computed from
events.json, tracking.csv and stats_per_minute.json; nothing is typed by hand.
This is a stand-in for the Stats Engine's FactSheet builder (Bryan): same shape,
fewer facts.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "output")
SCRIPT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "script", "match_script.json")
OUT = os.path.join(ROOT, "fixtures", "moments")

events = json.load(open(os.path.join(SRC, "events.json")))
per_min = json.load(open(os.path.join(SRC, "stats_per_minute.json")))
script = json.load(open(SCRIPT))

TEAM = {"KBA": "kba", "NGR": "ngr"}
NAME = {"KBA": "Kingsbridge", "NGR": "Northgate"}
OTHER = {"KBA": "NGR", "NGR": "KBA"}

players = {}
for side in ("home", "away"):
    for p in script["teams"][side]["players"]:
        surname = " ".join(p["name"].split(" ")[1:]) or p["name"]
        players[p["id"]] = {"surname": surname, "no": p["no"], "gk": p["pos"] == "GK"}


def _mins(minute) -> int:
    """'45+3' -> 48, '68' -> 68."""
    base, _, extra = str(minute).partition('+')
    return int(base) + int(extra or 0)


def who(pid):
    p = players.get(pid)
    return f"{p['surname']} ({p['no']})" if p else pid


# tracking: frame -> pid -> (x, y)
track = defaultdict(dict)
with open(os.path.join(SRC, "tracking.csv")) as f:
    for row in csv.DictReader(f):
        if row["object_id"] != "ball":
            track[int(row["frame"])][row["object_id"]] = (float(row["x"]), float(row["y"]))
halftime = min(e["frame"] for e in events if e["period"] == 2)


def attacks_right(team, period):
    return (team == "KBA") == (period == 1)


def last_defender_m(team, frame, period):
    """Distance from own goal of the deepest outfield player of `team` at `frame`."""
    own_goal_x = 0 if attacks_right(team, period) else 105
    d = [abs(x - own_goal_x) for pid, (x, y) in track[frame].items() if pid.startswith(team) and not players[pid]["gk"]]
    return round(min(d)) if d else None


def cum(frame):
    p1 = [r for r in per_min if r["period"] == 1]
    p2 = [r for r in per_min if r["period"] == 2]
    return p1[min(len(p1) - 1, frame // 60)] if frame < halftime else p2[min(len(p2) - 1, (frame - halftime) // 60)]


def state(frame, score=None):
    r = cum(frame)
    return {
        "score": score or [r["KBA_score"], r["NGR_score"]],
        "playersOnPitch": [r["KBA_players_on_pitch"], r["NGR_players_on_pitch"]],
        "possession": [round(r["KBA_possession_pct_cum"], 1), round(r["NGR_possession_pct_cum"], 1)],
        "xg": [round(r["KBA_xg_cum"], 2), round(r["NGR_xg_cum"], 2)],
        "shots": [r["KBA_shots_cum"], r["NGR_shots_cum"]],
    }


def possession_minutes(team, period, m_from, m_to):
    """Average per-minute possession of `team` over whole match minutes m_from..m_to (inclusive)."""
    rows = [r[f"{team}_possession_pct_minute"] for r in per_min
            if r["period"] == period and r["minute_index"] and m_from <= r["minute_index"] <= m_to]
    return round(sum(rows) / len(rows)) if rows else 0


def count(etype, team, a, b, cond=lambda e: True):
    return sum(1 for e in events if e["type"] == etype and e.get("team") == team and a <= e["frame"] <= b and cond(e))


class Sheet:
    def __init__(self, moment):
        self.moment = moment
        self.facts = []

    def add(self, text, metric, value, unit=None, window=None, src=()):
        self.facts.append({"factId": f"F{len(self.facts) + 1}", "text": text, "metric": metric, "value": value,
                           "unit": unit, "window": window, "sourceEventIds": list(src)})

    def write(self, match_state):
        home, away = (TEAM[script["teams"][side]["id"]] for side in ("home", "away"))
        sheet = {"moment": self.moment, "matchState": match_state, "facts": self.facts,
                 "home": home, "away": away, "teamNames": {TEAM[k]: v for k, v in NAME.items()}}
        os.makedirs(OUT, exist_ok=True)
        path = os.path.join(OUT, f"{self.moment['momentId']}.json")
        json.dump(sheet, open(path, "w"), indent=1, ensure_ascii=False)
        return path


written = []
subs_on = {e["player_in_id"]: e for e in events if e["type"] == "substitution"}
cards = [e for e in events if e["type"] == "yellow_card"]

# ---------------------------------------------------------------- goals
for g in [e for e in events if e["type"] == "goal"]:
    team, fr, per = g["team"], g["frame"], g["period"]
    shot = next(s for s in events if s["type"] == "shot" and s["frame"] == fr and s["player_id"] == g["player_id"])
    assist = g.get("assist_id")
    head = f"Goal {NAME[team]}: {who(g['player_id'])}" + (f", assist {who(assist)}" if assist else "") + f". {NAME['KBA']} {g['score_home']}-{g['score_away']} {NAME['NGR']}"
    sh = Sheet({"momentId": f"goal-{g['minute'].replace('+', 'p')}", "t": fr, "minute": g["minute"], "kind": "goal",
                "team": TEAM[team], "playerId": g["player_id"], "headline": head})
    sh.add(f"Shot xG {shot['xg']:.2f}" + (f", xGOT {shot['xgot']:.2f}" if shot.get("xgot") is not None else ""), "shot_xg", round(shot["xg"], 2), src=[shot["event_id"]])
    sh.add(f"Shot from {shot['distance_m']:.1f} m with the {shot['body_part'].replace('_', ' ')}", "shot_distance", round(shot["distance_m"], 1), "m", src=[shot["event_id"]])
    # the move: on-ball events of the scoring team in the 25 s before the goal
    move = [e for e in events if e.get("team") == team and fr - 25 <= e["frame"] <= fr and e["type"] in ("pass", "cross", "interception", "ball_recovery", "take_on", "carry")]
    if move:
        steps, ids = [], []
        for e in move:
            label = {"pass": "pass", "cross": "cross", "interception": "interception", "ball_recovery": "ball recovery", "take_on": "dribble"}.get(e["type"], e["type"])
            if e["type"] == "pass" and e.get("pass_type") not in (None, "pass"):
                label = e["pass_type"].replace("_", " ")
            steps.append(f"{who(e['player_id'])} {label}")
            ids.append(e["event_id"])
        shown = steps[-4:]
        n_players = len({st.split(")")[0] for st in shown})  # "Visser (8" identifies a player
        sh.add(f"The move ({n_players} players, {len(shown)} actions): " + " → ".join(shown), "move", len(steps), src=ids[-4:])
        last_pass = next((e for e in reversed(move) if e["type"] in ("pass", "cross")), None)
        if last_pass:
            d = last_defender_m(OTHER[team], last_pass["frame"], per)
            if d is not None:
                sh.add(f"{NAME[OTHER[team]]}'s deepest defender was {d} m from goal when the last pass was played", "defensive_line", d, "m", src=[last_pass["event_id"]])
    if g["player_id"] in subs_on:
        s = subs_on[g["player_id"]]
        sh.add(f"{who(g['player_id'])} came on at {s['minute']}', {_mins(g['minute']) - _mins(s['minute'])} minutes before this goal", "scorer_sub_minute", s["minute"], src=[s["event_id"]])
    if assist and assist in subs_on:
        s = subs_on[assist]
        sh.add(f"{who(assist)} came on at {s['minute']}', {_mins(g['minute']) - _mins(s['minute'])} minutes before this goal", "assist_sub_minute", s["minute"], src=[s["event_id"]])
    st = state(fr, [g["score_home"], g["score_away"]])
    sh.add(f"xG so far: {NAME['KBA']} {st['xg'][0]:.2f}, {NAME['NGR']} {st['xg'][1]:.2f}", "xg_cum", st["xg"][0 if team == "KBA" else 1])
    written.append(sh.write(st))

# ---------------------------------------------------------------- Quiroga's yellow card (13')
q = next(e for e in cards if e["player_id"] == "NGR-02")
sh = Sheet({"momentId": "yellow-13", "t": q["frame"], "minute": q["minute"], "kind": "yellow_card", "team": "ngr",
            "playerId": "NGR-02", "headline": f"Yellow card for {who('NGR-02')}, {NAME['NGR']}"})
won = count("take_on", "KBA", 0, q["frame"], lambda e: e["player_id"] == "KBA-11" and e.get("outcome") == "success")
tried = count("take_on", "KBA", 0, q["frame"], lambda e: e["player_id"] == "KBA-11")
sh.add(f"Nakamura-Brooks (11) won {won} of {tried} dribbles before the card", "dribbles_won", won, src=[])
fouls = count("foul", "NGR", 0, q["frame"], lambda e: e["player_id"] == "NGR-02")
sh.add(f"Quiroga (2) committed {fouls} foul(s) before the booking", "fouls", fouls)
sh.add("Quiroga is Northgate's right-back, directly up against Nakamura-Brooks on Kingsbridge's left", "matchup", "Quiroga v Nakamura-Brooks")
written.append(sh.write(state(q["frame"])))

# ---------------------------------------------------------------- red card (53')
red = next(e for e in events if e["type"] == "red_card")
first_y = next(e for e in cards if e["player_id"] == red["player_id"] and not e.get("second_yellow"))
sh = Sheet({"momentId": "red-53", "t": red["frame"], "minute": red["minute"], "kind": "red_card", "team": "kba",
            "playerId": red["player_id"], "headline": f"Red card (second yellow) for {who(red['player_id'])}, {NAME['KBA']}"})
sh.add(f"Brannigan (6) was booked earlier, at {first_y['minute']}'", "first_yellow_minute", first_y["minute"], src=[first_y["event_id"]])
fouls = count("foul", "KBA", 0, red["frame"], lambda e: e["player_id"] == red["player_id"])
sh.add(f"Brannigan committed {fouls} fouls before the red card", "fouls", fouls)
passes = count("pass", "KBA", 0, red["frame"], lambda e: e["player_id"] == red["player_id"])
team_passes = count("pass", "KBA", 0, red["frame"])
sh.add(f"Brannigan made {passes} of Kingsbridge's {team_passes} passes so far ({round(100 * passes / team_passes)}%)", "pass_share", round(100 * passes / team_passes), "%")
red_min = int(red["minute"])
pb = possession_minutes("KBA", 2, 46, red_min - 1)
sh.add(f"Kingsbridge possession in the second half before the red card: {pb}%", "possession_window", pb, "%", window=f"46'–{red_min - 1}'")
written.append(sh.write(state(red["frame"])))

# ---------------------------------------------------------------- 62' update: ten men
fr62 = halftime + 17 * 60
sh = Sheet({"momentId": "update-63", "t": fr62, "minute": "63", "kind": "update", "team": "kba",
            "headline": "Ten minutes after the red card"})
pa = possession_minutes("KBA", 2, red_min, 62)
sh.add(f"Kingsbridge possession since the red card: {pa}%", "possession_window", pa, "%", window=f"{red['minute']}'–62'")
sh.add(f"Kingsbridge possession before it, in the second half: {pb}%", "possession_window", pb, "%", window=f"46'–{red_min - 1}'")
sk, sn = count("shot", "KBA", red["frame"], fr62), count("shot", "NGR", red["frame"], fr62)
sh.add(f"Shots since the red card: Kingsbridge {sk}, Northgate {sn}", "shots_window", sn, window=f"{red['minute']}'–62'")
written.append(sh.write(state(fr62)))

# ---------------------------------------------------------------- half time
fr = halftime - 1
st = state(fr)
sh = Sheet({"momentId": "half-time", "t": fr, "minute": "45+3", "kind": "update", "headline": f"Half time: {NAME['KBA']} {st['score'][0]}-{st['score'][1]} {NAME['NGR']}"})
sh.add(f"Possession: Kingsbridge {round(st['possession'][0])}%, Northgate {round(st['possession'][1])}%", "possession", round(st["possession"][0]), "%")
sh.add(f"Shots: Kingsbridge {st['shots'][0]}, Northgate {st['shots'][1]}", "shots", st["shots"][0])
sh.add(f"xG: Kingsbridge {st['xg'][0]:.2f}, Northgate {st['xg'][1]:.2f}", "xg", st["xg"][0])
big = [s for s in events if s["type"] == "shot" and s["frame"] < halftime and s.get("big_chance")]
sh.add(f"Big chances: Kingsbridge {sum(s['team'] == 'KBA' for s in big)}, Northgate {sum(s['team'] == 'NGR' for s in big)}", "big_chances", len(big))
written.append(sh.write(st))

print("\n".join(os.path.relpath(p, ROOT) for p in written))
