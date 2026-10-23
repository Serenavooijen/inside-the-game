"""Walking skeleton: fixture -> simulator -> bus, and the HTTP API around it."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.bus import EventBus
from app.fixture import MATCH_ID, GeneratorSource
from app.simulator import KEY_MOMENT_MAX_S, Simulator
from app.wire import minute_from_clock

FIRST_GOAL_T = 1394      # Adeyemi-Clarke 0-1, event 688


def drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


@pytest.fixture
def sim():
    bus = EventBus(maxsize=10_000)
    s = Simulator(bus, {MATCH_ID: GeneratorSource})
    q = bus.subscribe()
    asyncio.run(s.load(MATCH_ID, "replay"))
    return s, q


def test_load_publishes_state_and_starts_playing(sim):
    s, q = sim
    [(name, data)] = drain(q)
    assert name == "state"
    assert data["matchId"] == "kba-ngr" and data["generation"] == 1
    assert data["duration"] == 5821 and data["halftime"] == 2821
    assert len(data["frame"]["players"]) == 22
    assert {m["kind"] for m in data["markers"]} == {"goal", "card", "red"}
    assert s.playing and s.speed == 10


def test_one_tick_per_match_second(sim):
    s, q = sim
    drain(q)
    s.step(0.5)                                    # 0.5 s real at 10x = 5 match seconds
    ticks = [d for n, d in drain(q) if n == "tick"]
    assert [t["t"] for t in ticks] == [5]          # one tick per new second reached in this step
    s.step(0.1)
    assert [d["t"] for n, d in drain(q) if n == "tick"] == [6]


def test_full_match_stats_match_the_analysis(sim):
    s, _ = sim
    s.seek(s.duration)
    stats = s.tick().stats
    assert stats.score == (2, 2)
    assert stats.xg == (2.48, 1.52)                # MATCH_ANALYSIS.md: xG 2.48 - 1.52
    assert stats.possession == (58, 42)            # 57.8% possession


def test_goal_event_starts_key_moment_at_1x(sim):
    s, q = sim
    s.seek(FIRST_GOAL_T - 1)
    drain(q)
    s.step(0.2)
    msgs = drain(q)
    goal = next(d for n, d in msgs if n == "event")
    assert goal["kind"] == "goal" and goal["id"] == "e-688" and goal["key"] is True
    assert goal["detail"].startswith("Adeyemi-Clarke (9)")
    tick = [d for n, d in msgs if n == "tick"][-1]
    assert tick["keyMomentId"] == "e-688" and tick["speed"] == 1 and tick["stats"]["score"] == [0, 1]


def test_key_moment_ends_on_insight_or_safety_net(sim):
    s, _ = sim
    s.seek(FIRST_GOAL_T - 1)
    s.step(0.2)
    s.set_speed(10)                                # remembered for after the key moment
    assert s.speed == 1
    s.end_key_moment("e-688")
    assert s.key_moment_id is None and s.speed == 10

    s.seek(FIRST_GOAL_T - 1)
    s.step(0.2)
    s.step(KEY_MOMENT_MAX_S)
    assert s.key_moment_id is None


def test_seek_raises_generation_and_recomputes(sim):
    s, q = sim
    drain(q)
    s.seek(FIRST_GOAL_T + 10)
    [(name, data)] = drain(q)
    assert name == "state" and data["generation"] == 2
    assert data["stats"]["score"] == [0, 1]
    assert [e["id"] for e in data["events"]][-1] == "e-688"
    s.seek(0)
    assert s.state().events == [] and s.tick().stats.score == (0, 0)


def test_pause_stops_time(sim):
    s, _ = sim
    s.pause()
    s.step(1.0)
    assert s.t == 0


def test_bus_drops_oldest_when_a_subscriber_is_slow():
    bus = EventBus(maxsize=2)
    q = bus.subscribe()
    for i in range(3):
        bus.publish("tick", {"t": i})
    assert [d["t"] for _, d in drain(q)] == [1, 2]


@pytest.mark.parametrize("clock, minute", [("00:00", "1"), ("23:14", "24"), ("45+1:30", "45+2"), ("90+4:59", "90+5")])
def test_minute_labels(clock, minute):
    assert minute_from_clock(clock) == minute


def test_api_round_trip():
    from app.main import app
    with TestClient(app) as client:
        assert client.get("/state").status_code == 409
        assert client.post("/match/load", json={"match_id": "nope"}).status_code == 404
        assert client.post("/match/load", json={"match_id": "kba-ngr", "mode": "live"}).json() == {"ok": True}
        assert client.post("/pause").status_code == 200
        assert client.post("/speed", json={"factor": 1}).status_code == 200
        assert client.post("/speed", json={"factor": 3}).status_code == 422
        assert client.post("/seek", json={"t": 4138}).status_code == 200
        state = client.get("/state").json()
        assert state["t"] == 4138 and state["mode"] == "live" and "markers" not in state
        assert state["speed"] == 1 and state["playing"] is False
        assert client.get("/matches").json()[0]["id"] == "kba-ngr"
        cors = client.options("/seek", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
        assert cors.headers["access-control-allow-origin"] == "http://localhost:3000"
