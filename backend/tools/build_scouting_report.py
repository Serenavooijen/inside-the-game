"""
Builds the Scout's report on the cup match: fixtures/scouting/kba-ngr-cup.json.

The facts (ids C1, C2, ...) are the cup match's tactical fingerprint over the whole
match, plus its formation changes and substitutions. They are the baseline for every
live tactical analysis. The Scout writes 4-6 checked observations from them, once,
before kick-off.

    cd backend
    uv run python ../generator/generate_match.py ../script/cup/match_script.json ../output/cup   # once
    uv run python tools/build_scouting_report.py                         # MODEL_PROVIDER from the environment
    uv run python tools/build_scouting_report.py --provider foundry-agents
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

from app.agents.llm import model_from_env  # noqa: E402
from app.agents.playbook import visible_to_scout  # noqa: E402
from app.agents.scout import check_observation, run_scout  # noqa: E402
from app.contracts import (  # noqa: E402
    Fact, ScoutingReport, SourceEvent, SourceFrame, TacticalFactSheet, TacticalWindow,
)
from app.fixture import load_generated  # noqa: E402
from app.tactics import Tactician  # noqa: E402
from app.wire import team_id  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "fixtures" / "scouting" / "kba-ngr-cup.json"
REPORT_ID = "kba-ngr-cup"
MAX_OBSERVATIONS = 6


def cup_sheet() -> tuple[TacticalFactSheet, Tactician, list[SourceFrame]]:
    info, roster, items = load_generated(ROOT / "output" / "cup", ROOT / "script" / "cup" / "match_script.json", REPORT_ID)
    frames = [i for i in items if isinstance(i, SourceFrame)]
    events = [i for i in items if isinstance(i, SourceEvent)]
    tac = Tactician(info, roster, frames)
    end = frames[-1].t
    facts = tac.baseline_facts(events, 0, end)

    # What changed during the cup match: formation changes and the effect of each team's substitutions.
    subs: dict[tuple[float, str], list[SourceEvent]] = {}
    for e in events:
        if e.type == "substitution":
            subs.setdefault((e.t, e.team), []).append(e)
    extra = tac.shape_changes(events, 0, end) + tac.event_states(events, 0, end)
    for group in subs.values():
        extra += [d for d in tac.substitution(group, events, min(end, group[0].t + 600)) if d.change]
    for d in extra:
        facts.append(Fact(fact_id=f"C{len(facts) + 1}", text=f"Cup match: {d.text}", metric=d.metric, value=d.value,
                          unit=d.unit, window="cup match", source_event_ids=d.src, team=team_id(d.team), concept=d.concept))

    goals = [e for e in events if e.type == "goal"]
    home, away = team_id(info.home), team_id(info.away)
    names = {home: info.team_names[info.home], away: info.team_names[info.away]}
    score = f"{goals[-1].score_home}-{goals[-1].score_away}" if goals else "0-0"
    sheet = TacticalFactSheet(
        window=TacticalWindow(from_t=0, to_t=end, label="cup match"), trigger="scouting", minute="90",
        headline=f"Scouting report, cup match: {names[home]} {score} {names[away]}",
        home=home, away=away, team_names=names, facts=facts,
        concepts_fired=list(dict.fromkeys(f.concept for f in facts if f.concept)),
    )
    return sheet, tac, frames


async def build(provider: str | None, deadline: float) -> ScoutingReport:
    sheet, tac, frames = cup_sheet()
    model = model_from_env(provider)
    warm = getattr(model, "warmup", None)
    if warm:
        await warm()

    # Two passes give 4-6 observations: one per team, each only with that team's facts.
    observations, rejected, statuses = [], [], []
    for team in (sheet.home, sheet.away):
        # The Scout only sees what the team did: a 5% "dropping 6" is not a plan (it stays in the baseline).
        shown = [f for f in sheet.facts if f.team == team and visible_to_scout(f)]
        part = sheet.model_copy(update={"facts": shown})
        part = part.model_copy(update={"concepts_fired": list(dict.fromkeys(f.concept for f in part.facts))})
        insight = await run_scout(part, None, model=model, deadline_s=deadline)
        statuses.append(insight.status)
        rejected += insight.rejected_claims
        observations += [o.model_copy(update={"compare_to_cup": "n/a"}) for o in insight.observations or []]
        print(f"{team}: {insight.status} · {insight.latency_ms} ms · {len(insight.observations or [])} observations")

    # Re-check against the full sheet (the ids are the same), and keep at most six.
    checked, more = [], []
    for o in observations:
        ok, rej = check_observation(o, sheet)
        more += rej
        if ok:
            checked.append(ok)
    observations = checked
    status = "fallback" if "fallback" in statuses else "corrected" if rejected or more else "checked"
    ht = next(f.t for f in frames if f.period == 2) - 1
    return ScoutingReport(
        id=REPORT_ID, title=sheet.headline.removeprefix("Scouting report, ").replace("cup match", "Cup round 2"),
        home=sheet.home, away=sheet.away, observations=observations[:MAX_OBSERVATIONS], facts=sheet.facts,
        status=status, rejected_claims=rejected + more,
        heatmaps=[h for t in (sheet.home, sheet.away) if (h := tac.heatmap(t.upper(), 0, ht))],
        generated_by=getattr(model, "name", None),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=None)
    ap.add_argument("--deadline", type=float, default=30.0)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    report = asyncio.run(build(args.provider, args.deadline))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    import json
    out.write_text(json.dumps(report.to_json(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n{report.title} · {report.status} · {len(report.observations)} observations · {len(report.facts)} facts")
    for o in report.observations:
        print(f"  • [{o.team}] {o.observation} {o.fact_ids}\n    Consequence: {o.consequence}"
              + (f"\n    For the coach: {o.coach_action}" if o.coach_action else ""))
    for r in report.rejected_claims:
        print(f"  ✗ {r.text}\n    {r.reason}")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
