"""Substitution facts (G2, G4) on the substitutions of the reference match: 46', 59', 64', 76', 87'."""
import json
from functools import lru_cache

import pytest

from app.agents.checker import check_text, unknown_names
from app.agents.models import Claim
from app.agents.playbook import concept_terms
from app.contracts import ScoutingReport, SourceEvent, SourceFrame
from app.fixture import SCOUTING_REPORT
from app.tactics import Tactician

from .test_tactics import match

KINDS_AT_THE_MOMENT = {"46": "like-for-like", "59": "like-for-like", "64": "shape change", "76": "shape change",
                       "87": "shape change"}


@lru_cache(maxsize=1)
def setup():
    report = ScoutingReport.model_validate(json.loads(SCOUTING_REPORT.read_text(encoding="utf-8")))
    info, roster, frames, events = match("today")
    tac = Tactician(info, roster, frames, report.facts)
    moments: dict[tuple[float, str], list[SourceEvent]] = {}
    for e in events:
        if e.type == "substitution":
            moments.setdefault((e.t, e.team), []).append(e)
    return tac, events, frames, list(moments.values())


def by_minute(minute: str):
    tac, events, frames, moments = setup()
    return tac, events, next(m for m in moments if m[0].minute == minute)


def test_five_substitution_moments():
    *_, moments = setup()
    assert [m[0].minute for m in moments] == ["46", "59", "64", "76", "87"]
    assert [len(m) for m in moments] == [1, 1, 2, 2, 1]


@pytest.mark.parametrize("minute", list(KINDS_AT_THE_MOMENT))
def test_watch_sheet_who_kind_state_and_backed_watch_points(minute):
    tac, events, subs = by_minute(minute)
    sheet = tac.substitution_sheet(subs, events, subs[0].t + 2, "watch")
    info = sheet.substitution
    assert info.stage == "watch" and info.kind == KINDS_AT_THE_MOMENT[minute]
    assert len(info.off) == len(info.on) == len(subs)
    assert all(p.role and p.n for p in info.off + info.on)
    texts = [f.text for f in sheet.facts]
    assert texts[0].startswith(f"At {minute}' ") and any(" → " in t for t in texts)
    # Every number and every name in the watch points stands in a fact
    claims = [Claim(text=f.text, fact_ids=[f.fact_id]) for f in sheet.facts]
    assert 1 <= len(info.watch) <= 2
    for w in info.watch:
        assert check_text(w, sheet, [f.fact_id for f in sheet.facts]) == [], w
        assert unknown_names(w, sheet, claims, concept_terms()) == [], w


def test_the_watch_sheet_only_uses_the_past():
    tac, events, subs = by_minute("64")
    info, roster, frames, _ = match("today")
    t = subs[0].t + 2
    short = Tactician(info, roster, [f for f in frames if f.t <= t], tac.baseline)
    a = tac.substitution_sheet(subs, events, t, "watch")
    b = short.substitution_sheet(subs, [e for e in events if e.t <= t], t, "watch")
    assert a.to_json() == b.to_json()


def test_why_the_players_went_off():
    tac, events, subs = by_minute("46")
    texts = [f.text for f in tac.substitution_sheet(subs, events, subs[0].t + 2, "watch").facts]
    assert "Quiroga (2) went off on a yellow card from 13'" in texts
    assert any(t.startswith("Quiroga (2), full-back, off; Whitfield (22), full-back, on at 46'") for t in texts)
    tac, events, subs = by_minute("87")
    texts = [f.text for f in tac.substitution_sheet(subs, events, subs[0].t + 2, "watch").facts]
    assert any("intensity dropped by" in t for t in texts) and any(t.endswith("; low involvement") for t in texts)
    assert "Northgate changed from a 4-3-3 to a 5-4-1 with the change at 87'" in texts


@pytest.mark.parametrize("minute", list(KINDS_AT_THE_MOMENT))
def test_impact_sheet_after_8_minutes(minute):
    tac, events, subs = by_minute(minute)
    sheet = tac.substitution_sheet(subs, events, subs[0].t + 480, "impact")
    info = sheet.substitution
    texts = " ".join(f.text for f in sheet.facts)
    assert info.stage == "impact" and len(info.heatmaps) == 2 and len(info.heatmap_labels) == 2
    assert all(h.dir == 1 for h in info.heatmaps)                # team-relative
    assert f"Since the change at {minute}'" in texts              # the effect on the team
    assert "In the cup match" in texts                            # the comparison with the cup match
    assert any(f.metric.startswith("sub_on_") for f in sheet.facts)


def test_impact_details():
    tac, events, subs = by_minute("64")
    texts = [f.text for f in tac.substitution_sheet(subs, events, subs[0].t + 480, "impact").facts]
    assert "Halvorsen (18) plays 4 m higher and 7 m more central than Moreau (7) did" in texts
    assert "Since the change at 64', Northgate's build-up shape is 2-3-2-3, before 2-2-4-2" in texts
    assert "In the cup match Northgate also changed at a similar moment, 61': Northgate changed from a 4-3-3 to a 4-4-2 at 61'" in texts
    tac, events, subs = by_minute("46")
    texts = [f.text for f in tac.substitution_sheet(subs, events, subs[0].t + 480, "impact").facts]
    # the opponent changed in the same period because of a red card: said neutrally, with the cause
    assert "In the same period Kingsbridge changed from a 4-3-3 to a 4-4-1 at 53', after a red card at 53'" in texts
    tac, events, subs = by_minute("59")
    texts = [f.text for f in tac.substitution_sheet(subs, events, subs[0].t + 480, "impact").facts]
    assert any(t.startswith("Northgate made a substitution of their own within 5 minutes, at 64'") for t in texts)
