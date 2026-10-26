"""Tactician: detectors on a small synthetic stretch of tracking, and on the generated matches
(the cup match has its tactical behaviour scripted in meta.scripted_tactics)."""
import json
from functools import lru_cache
from pathlib import Path

import pytest

from app.contracts import MatchInfo, SourceBall, SourceEvent, SourceFrame, SourcePlayer
from app.fixture import load_generated
from app.sources import PlayerInfo
from app.tactics import Tactician, formation_of, shape_of

ROOT = Path(__file__).resolve().parents[2]
INFO = MatchInfo(match_id="t", title="t", home="HOM", away="AWY", team_names={"HOM": "Home", "AWY": "Away"})

# Home attacks towards x 105 in the first half; positions are absolute = team-relative for home.
HOME_442 = {"GK": (5, 34), "RB": (30, 8), "RCB": (22, 26), "LCB": (22, 42), "LB": (30, 60), "DM": (36, 34),
            "RCM": (45, 22), "LCM": (45, 46), "RW": (60, 10), "ST": (65, 34), "LW": (60, 58)}
AWAY = {"GK": (100, 34), "RB": (75, 60), "RCB": (82, 42), "LCB": (82, 26), "LB": (75, 8), "RM": (65, 60),
        "RCM": (66, 40), "LCM": (66, 28), "LM": (65, 8), "RS": (55, 38), "LS": (55, 30)}


def roster() -> dict[str, PlayerInfo]:
    out = {}
    for team, shape in (("HOM", HOME_442), ("AWY", AWAY)):
        for n, role in enumerate(shape, start=1):
            pid = f"{team}-{role}"
            out[pid] = PlayerInfo(id=pid, team=team, n=n, name=role, surname=role.title(), gk=role == "GK")
    return out


def frames(n: int, dm_between: bool, start: int = 0) -> list[SourceFrame]:
    """`n` seconds of the home team in possession in its own half, the 6 dropping in or not."""
    out = []
    for t in range(start, start + n):
        home = dict(HOME_442)
        if dm_between:
            home.update(DM=(22, 34), RCB=(20, 16), LCB=(20, 52), RB=(45, 6), LB=(45, 62))  # full-backs push on
        # a new build-up phase every 10 s: the away team touches the ball once in between
        holder = "AWY-RS" if t % 10 == 0 else "HOM-RCB"
        players = [SourcePlayer(id=f"HOM-{r}", team="HOM", role=r, x=x, y=y, speed=0) for r, (x, y) in home.items()]
        players += [SourcePlayer(id=f"AWY-{r}", team="AWY", role=r, x=x, y=y, speed=0) for r, (x, y) in AWAY.items()]
        out.append(SourceFrame(t=t, period=1, clock=f"{t // 60:02d}:{t % 60:02d}", players=players,
                               ball=SourceBall(x=25, y=30, live=True, holder_id=holder)))
    return out


def test_dropping_six_fires_b1_with_the_count_in_the_text():
    tac = Tactician(INFO, roster(), frames(300, dm_between=True))
    sheet = tac.sheet("interval", 0, 299, [])
    b1 = next(f for f in sheet.facts if f.concept == "B1")
    assert b1.team == "hom" and b1.value == 100
    assert "Dm (6)" in b1.text and "100% of 30 build-up phases" in b1.text
    assert "3 in the last line in build-up" in b1.text
    assert sheet.window.label == "0'–5'" and "B1" in sheet.concepts_fired


def test_a_six_that_stays_in_front_does_not_fire_b1_without_a_baseline():
    tac = Tactician(INFO, roster(), frames(300, dm_between=False))
    sheet = tac.sheet("interval", 0, 299, [])
    assert not sheet or all(f.concept != "B1" for f in sheet.facts)


def test_a_change_against_the_previous_window_is_a_fact_with_the_difference():
    tac = Tactician(INFO, roster(), frames(300, dm_between=True) + frames(300, dm_between=False, start=300))
    sheet = tac.sheet("interval", 300, 599, [], prev=(0, 299))
    b1 = next(f for f in sheet.facts if f.concept == "B1")
    assert b1.value == 0
    assert "(previous 5 minutes: 100%, down 100 points)" in b1.text


def test_baseline_facts_are_cited_next_to_the_live_fact():
    cup = Tactician(INFO, roster(), frames(300, dm_between=True))
    baseline = cup.baseline_facts([], 0, 299)
    live = Tactician(INFO, roster(), frames(300, dm_between=False), baseline)
    sheet = live.sheet("interval", 0, 299, [])
    b1 = next(f for f in sheet.facts if f.concept == "B1")
    assert "cup match: 100%, down 100 points" in b1.text
    assert [b.metric for b in sheet.baseline if b.concept == "B1"] == ["dm_between_pct"]
    assert all(b.fact_id.startswith("C") for b in sheet.baseline)
    assert sheet.fact(sheet.baseline[0].fact_id) is sheet.baseline[0]


def test_only_the_past_counts():
    """A sheet for [0, 299] is the same whether or not later frames exist (live = replay)."""
    early = frames(300, dm_between=True)
    later = early + frames(300, dm_between=False, start=300)
    a = Tactician(INFO, roster(), early).sheet("interval", 0, 299, [])
    b = Tactician(INFO, roster(), later).sheet("interval", 0, 299, [])
    assert a.to_json() == b.to_json()


def test_shape_and_formation_helpers():
    assert shape_of([20, 20, 21, 21, 40, 41, 42, 60, 61, 62]) == "4-3-3"
    assert shape_of([20, 21, 22, 30, 31, 32, 33, 34, 50, 51]) == "3-5-2"
    assert formation_of(["GK", "RB", "RCB", "LCB", "LB", "DM", "RCM", "LCM", "RW", "ST", "LW"]) == "4-3-3"
    assert formation_of(["GK", "RCB", "CB", "LCB", "RWB", "RCM", "LCM", "LWB", "RS", "LS"]) == "3-4-2"
    assert formation_of(["GK", "RWB", "RCB", "CB", "LCB", "LWB", "RM", "RCM", "LCM", "LM", "ST"]) == "5-4-1"


# ------------------------------------------------------------------ the generated matches

@lru_cache(maxsize=2)
def match(which: str):
    out, script = {"cup": ("output/cup", "script/cup/match_script.json"),
                   "today": ("output", "script/match_script.json")}[which]
    info, roster_, items = load_generated(ROOT / out, ROOT / script, which)
    fs = [i for i in items if isinstance(i, SourceFrame)]
    evs = [i for i in items if isinstance(i, SourceEvent)]
    return info, roster_, fs, evs


def t_at(fs: list[SourceFrame], minute: int) -> float:
    clock = f"{minute:02d}:00"
    return next(f.t for f in fs if f.clock == clock)


def scripted(concept: str, team: str) -> dict:
    meta = json.loads((ROOT / "script" / "cup" / "match_script.json").read_text(encoding="utf-8"))["meta"]
    return next(s for s in meta["scripted_tactics"] if s["concept"] == concept and s["team"] == team)


def test_cup_detectors_find_the_scripted_dropping_six():
    info, roster_, fs, evs = match("cup")
    story = scripted("B1", "NGR")
    tac = Tactician(info, roster_, fs)
    during = tac.prints(t_at(fs, story["from"]) if story["from"] else 0, t_at(fs, story["to"]) - 1, evs)["NGR"]
    after = tac.prints(t_at(fs, story["to"]) + 30, fs[-1].t, evs)["NGR"]
    assert during.dm_between >= 40 and during.dm_id == story["player"]
    assert after.dm_between is None                 # 4-4-2 from 60': no 6 any more


def test_cup_detectors_find_the_scripted_inverted_full_back_and_its_end():
    info, roster_, fs, evs = match("cup")
    story = scripted("B3", "KBA")
    tac = Tactician(info, roster_, fs)
    during = tac.prints(0, t_at(fs, story["to"]) - 1, evs)["KBA"]
    after = tac.prints(t_at(fs, story["to"]) + 30, fs[-1].t, evs)["KBA"]
    assert during.fb_invert["LB"] == (story["player"], during.fb_invert["LB"][1])
    assert during.fb_invert["LB"][1] >= 30
    assert after.fb_invert["LB"][1] < 20 and after.fb_invert["LB"][0] == scripted("G2", "KBA")["player"]


def test_cup_formation_change_at_the_hour_is_a_g1_fact():
    info, roster_, fs, evs = match("cup")
    tac = Tactician(info, roster_, fs)
    sheet = tac.sheet("interval", t_at(fs, 60), t_at(fs, 65), evs)
    g1 = next(f for f in sheet.facts if f.concept == "G1")
    assert g1.text == "Northgate changed from a 4-3-3 to a 4-4-2 at 61'" and g1.team == "ngr"


def test_today_against_the_cup_baseline_and_a_substitution():
    cup_info, cup_roster, cup_fs, cup_evs = match("cup")
    baseline = Tactician(cup_info, cup_roster, cup_fs).baseline_facts(cup_evs, 0, cup_fs[-1].t)
    info, roster_, fs, evs = match("today")
    tac = Tactician(info, roster_, fs, baseline)
    subs = [e for e in evs if e.type == "substitution" and e.minute == "64"]
    sheet = tac.sheet("substitution", subs[0].t, subs[0].t + 180, evs, subs=subs)
    texts = [f.text for f in sheet.facts]
    assert texts[0].startswith("Since Halvorsen (18) and Diallo-Kerr (20) came on at 64'")
    assert "Northgate changed from a 4-4-2 to a 4-3-3 at 64'" in texts
    assert sheet.facts[0].concept == "G2" and set(sheet.facts[0].source_event_ids) == {e.event_id for e in subs}
    # Later, with a 6 again: B1 compares with the cup match
    later = tac.sheet("interval", t_at(fs, 65), t_at(fs, 70), evs, prev=(t_at(fs, 60), t_at(fs, 65) - 1))
    b1 = next(f for f in later.facts if f.concept == "B1" and f.team == "ngr")
    assert "Duarte (8)" in b1.text and "cup match: 58%" in b1.text
    assert any(b.metric == "dm_between_pct" and b.team == "ngr" for b in later.baseline)
    assert [f.fact_id for f in later.facts] == [f"T{i}" for i in range(1, len(later.facts) + 1)]
    assert all(f.concept and f.team for f in later.facts)


@pytest.mark.parametrize("minute", [10, 30, 60, 70, 85])
def test_every_window_of_today_builds_a_short_sheet(minute):
    info, roster_, fs, evs = match("today")
    tac = Tactician(info, roster_, fs)
    sheet = tac.sheet("interval", t_at(fs, minute - 5) + 1, t_at(fs, minute), evs,
                      prev=(t_at(fs, minute - 10) + 1, t_at(fs, minute - 5)))
    assert sheet is not None and 1 <= len(sheet.facts) <= 12
    assert sheet.window.label == f"{minute - 5}'–{minute}'"


def test_block_height_is_measured_with_the_ball_in_midfield():
    """Over all out-of-possession frames Northgate's line reads 15-17 m because the ball sat deep in their half;
    with the ball in the middle third it is the block they chose: about 20 m today, about 28 m in the cup."""
    info, roster_, fs, evs = match("today")
    today = Tactician(info, roster_, fs).prints(0, fs[-1].t, evs)
    c_info, c_roster, c_fs, c_evs = match("cup")
    cup = Tactician(c_info, c_roster, c_fs).prints(0, c_fs[-1].t, c_evs)
    assert 19 <= today["NGR"].line_m <= 25 and 25 <= cup["NGR"].line_m <= 31
    assert today["KBA"].line_m >= 33                       # Kingsbridge's high block
    sheet = Tactician(info, roster_, fs).sheet("interval", t_at(fs, 5) + 1, t_at(fs, 10), evs)
    d1 = next(f for f in sheet.facts if f.concept == "D1" and f.team == "kba")
    assert "with the ball in midfield" in d1.text
