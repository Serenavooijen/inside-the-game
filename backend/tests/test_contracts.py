"""The contracts must fit the data that already exists: generator output (source layer),
Serena's test moments (agents layer) and the frontend recording (wire layer)."""
import csv
import json
from pathlib import Path

import pytest

from app.contracts import (
    FactSheet,
    Frame,
    Insight,
    MatchEvent,
    MatchSnapshot,
    MatchStats,
    Moment,
    Overlay,
    Player,
    Point,
    SourceBall,
    SourceEvent,
    SourceFrame,
    SourcePlayer,
    Tick,
)
from app.fixture import to_source_event

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "output"
MOMENTS = sorted((ROOT / "fixtures" / "moments").glob("*.json"))
RECORDING = ROOT / "frontend" / "data" / "matches" / "kba-ngr.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ source layer

def test_every_generated_event_fits_source_event():
    rows = load(OUTPUT / "events.json")
    events = [to_source_event(r) for r in rows]
    assert len(events) == len(rows)
    goals = [e for e in events if e.type == "goal"]
    assert (goals[-1].score_home, goals[-1].score_away) == (2, 2)
    assert goals[0].details["assist_id"] == "NGR-08"
    assert goals[0].details["scripted"] is True


def test_tracking_rows_fit_source_frame():
    with open(OUTPUT / "tracking.csv", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["frame"] == "0"]
    ball = next(r for r in rows if r["object_id"] == "ball")
    frame = SourceFrame(
        t=0, period=1, clock=ball["clock"],
        players=[
            SourcePlayer(id=r["object_id"], team=r["team"], role=r["role_or_state"],
                         x=r["x"], y=r["y"], speed=r["speed_ms_or_ball_holder"])
            for r in rows if r["object_id"] != "ball"
        ],
        ball=SourceBall(x=ball["x"], y=ball["y"], live=ball["role_or_state"] == "live",
                        holder_id=ball["speed_ms_or_ball_holder"] or None),
    )
    assert len(frame.players) == 22
    assert frame.ball.holder_id == "KBA-09"


def test_live_feed_shapes_are_accepted():
    event = SourceEvent(
        event_id=1, t=6123.48, period=3, second_in_period=123.48, clock="90:02", minute="91",
        type="other", team="ARS", score_home=1, score_away=1,
        details={"provider_type": "Shield", "provider_event_id": "a3f1-uuid"},
    )
    assert event.possession_seq is None


# ------------------------------------------------------------------ agents layer

@pytest.mark.parametrize("path", MOMENTS, ids=lambda p: p.stem)
def test_test_moments_round_trip_as_fact_sheet(path):
    raw = load(path)
    assert _same_ignoring_nulls(FactSheet.model_validate(raw).to_json(), raw)


def _same_ignoring_nulls(a, b) -> bool:
    """Equal after dropping nulls (to_json omits them)."""
    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if v is not None}
        if isinstance(x, list):
            return [strip(v) for v in x]
        return x
    return strip(a) == strip(b)


def test_team_ids_are_not_fixed_to_one_match():
    moment = Moment(moment_id="g1", t=10, minute="1", kind="goal", team="hv", headline="Goal Harlow Vale")
    assert moment.team == "hv"


# ------------------------------------------------------------------ wire layer

@pytest.fixture(scope="module")
def recording():
    return load(RECORDING)


@pytest.mark.parametrize("model, key", [(MatchEvent, "events"), (Overlay, "overlays"), (Insight, "insights")])
def test_frontend_recording_round_trips(recording, model, key):
    """Every field the frontend already plays must survive Python unchanged.
    Python may add defaults (generation, phase, empty traceability lists)."""
    for raw in recording[key]:
        out = model.model_validate(raw).to_json()
        assert {k: out.get(k) for k in raw} == raw, raw["id"]


def test_tick_serialises_to_frontend_shape():
    tick = Tick(
        t=760, period=1, clock="12:40", minute="13", speed=10, playing=True, generation=2,
        frame=Frame(t=760, players=[Player(id="KBA-01", team="kba", n=1, x=5.2, y=34.0, gk=True)],
                    ball=Point(x=70, y=58)),
        stats=MatchStats(score=(0, 0), xg=(0.21, 0.05), possession=(58.0, 42.0)),
    )
    data = tick.to_json()
    assert data["stats"]["score"] == [0, 0]
    assert data["frame"]["players"][0] == {"id": "KBA-01", "team": "kba", "n": 1, "x": 5.2, "y": 34.0, "gk": True}
    assert "keyMomentId" not in data          # frontend reads it as `?? null`
    assert data["finished"] is False


def test_overlay_from_field_uses_reserved_word():
    o = Overlay(id="o1", t=5, slot="sprint", player_id="KBA-07", value=33.1, from_=Point(x=1, y=2))
    assert o.to_json()["from"] == {"x": 1, "y": 2}
    assert Overlay.model_validate(o.to_json()).from_ == Point(x=1, y=2)


def test_snapshot_serialises_as_match_state_key():
    snap = MatchSnapshot(score=(1, 2), possession=(56.6, 43.4), xg=(1.35, 0.99), shots=(13, 9))
    sheet = FactSheet(moment=Moment(moment_id="m", t=1, minute="1", kind="update", headline="h"),
                      match_state=snap, facts=[], home="hv", away="su",
                      team_names={"hv": "Harlow Vale", "su": "Saltmarsh United"})
    assert "matchState" in sheet.to_json()
    assert sheet.home_away == ("Harlow Vale", "Saltmarsh United")


def test_fact_sheet_needs_a_name_for_both_teams():
    with pytest.raises(ValueError, match="no name for"):
        FactSheet(moment=Moment(moment_id="m", t=1, minute="1", kind="update", headline="h"),
                  match_state=MatchSnapshot(score=(0, 0), possession=(50, 50), xg=(0, 0), shots=(0, 0)),
                  facts=[], home="hv", away="su", team_names={"hv": "Harlow Vale"})


# ------------------------------------------------------------------ tactics (v0.4)

def test_tactical_fact_sheet_finds_live_and_baseline_facts():
    from app.contracts import Fact, TacticalFactSheet, TacticalWindow
    sheet = TacticalFactSheet(
        window=TacticalWindow(from_t=3600, to_t=3900, label="60'–65'"), trigger="interval", minute="65",
        headline="Tactics 60'–65'", home="kba", away="ngr", team_names={"kba": "Kingsbridge", "ngr": "Northgate"},
        facts=[Fact(fact_id="T1", text="6 drops in 0% of build-ups", metric="dm_drop_between", value=0, team="ngr", concept="B1")],
        baseline=[Fact(fact_id="C1", text="Cup: 6 drops in 71% of build-ups", metric="dm_drop_between", value=71)],
    )
    assert sheet.fact("T1").concept == "B1" and sheet.fact("C1").value == 71
    data = sheet.to_json()
    assert data["window"] == {"fromT": 3600, "toT": 3900, "label": "60'–65'"}
    assert data["facts"][0]["concept"] == "B1"


def test_tactics_insight_and_commentary_serialise_to_frontend_shape():
    from app.contracts import Commentary, Heatmap, TacticalObservation, TacticalWindow
    i = Insight(id="i-tac-65", t=3900, minute="65", type="tactics", text="", trigger="interval",
                window=TacticalWindow(from_t=3600, to_t=3900, label="60'–65'"),
                observations=[TacticalObservation(observation="o", fact_ids=["T1"], consequence="c",
                                                  coach_action="a", compare_to_cup="changed", team="ngr")],
                heatmap=Heatmap(team="ngr", grid=[[0.0] * 6] * 4, dir=-1))
    data = i.to_json()
    assert data["observations"][0] == {"observation": "o", "factIds": ["T1"], "consequence": "c",
                                       "coachAction": "a", "compareToCup": "changed", "team": "ngr"}
    assert data["heatmap"]["dir"] == -1 and len(data["heatmap"]["grid"]) == 4
    c = Commentary(t=3910, minute="66", text="Northgate keep the ball wide.", source_insight_id="i-tac-65")
    assert c.to_json() == {"t": 3910, "minute": "66", "text": "Northgate keep the ball wide.",
                           "sourceInsightId": "i-tac-65", "generation": 0}
