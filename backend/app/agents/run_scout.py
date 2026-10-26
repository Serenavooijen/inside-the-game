"""
Run the Scout on the reference match: five 5-minute windows, half time and a substitution,
each with the cup-match baseline. Shows the checked observations per window.

    cd backend
    uv run python -m app.agents.run_scout                       # MODEL_PROVIDER from the environment
    uv run python -m app.agents.run_scout --provider offline
    uv run python -m app.agents.run_scout --provider foundry-agents --json scout.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.contracts import SourceEvent, SourceFrame
from app.fixture import load_generated
from app.tactics import Tactician

from .llm import model_from_env
from .scout import run_scout

ROOT = Path(__file__).resolve().parents[3]
WINDOWS = (15, 30, 60, 70, 80)       # end minute of each 5-minute window


def load(out: str, script: str, match_id: str):
    info, roster, items = load_generated(ROOT / out, ROOT / script, match_id)
    return (info, roster, [i for i in items if isinstance(i, SourceFrame)],
            [i for i in items if isinstance(i, SourceEvent)])


def t_at(frames: list[SourceFrame], minute: int, period: int) -> float:
    return next(f.t for f in frames if f.clock == f"{minute:02d}:00" and f.period == period)


def sheets():
    """(label, sheet, tactician) for the windows, half time and the 64' substitutions."""
    c_info, c_roster, c_frames, c_events = load("output/cup", "script/cup/match_script.json", "kba-ngr-cup")
    baseline = Tactician(c_info, c_roster, c_frames).baseline_facts(c_events, 0, c_frames[-1].t)
    info, roster, frames, events = load("output", "script/match_script.json", "kba-ngr")
    tac = Tactician(info, roster, frames, baseline)
    out = []
    for m in WINDOWS:
        period = 1 if m <= 45 else 2
        to = t_at(frames, m, period)
        frm = to - 299
        out.append((f"{m - 5}'–{m}'", tac.sheet("interval", frm, to, events, prev=(frm - 300, frm - 1)), tac))
    ht = next(e for e in events if e.type == "period_end" and e.period == 1)
    out.append(("half time", tac.sheet("half_time", 0, ht.t - 1, events), tac))
    subs = [e for e in events if e.type == "substitution" and e.minute == "64"]
    out.append(("subs 64'", tac.sheet("substitution", subs[0].t, subs[0].t + 180, events, subs=subs), tac))
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=None)
    ap.add_argument("--deadline", type=float, default=None)
    ap.add_argument("--json", default=None, help="write the insights to this file")
    args = ap.parse_args()
    model = model_from_env(args.provider)
    warm = getattr(model, "warmup", None)
    if warm:
        await warm()
    results = []
    for label, sheet, tac in sheets():
        if sheet is None:
            print(f"\n== {label}: no meaningful tactical facts")
            continue
        team = {f.team for f in sheet.facts}
        insight = await run_scout(sheet, None, model=model, deadline_s=args.deadline,
                                  heatmap=tac.heatmap(sheet.facts[0].team.upper(), sheet.window.from_t, sheet.window.to_t))
        results.append(insight.to_json())
        print(f"\n== {label} · {sheet.window.label} · {insight.status} · {insight.latency_ms} ms"
              f"{f' · {insight.tokens} tokens' if insight.tokens else ''} · concepts {sheet.concepts_fired} · teams {sorted(team)}")
        for o in insight.observations or []:
            print(f"  • [{o.team}] {o.observation}  {o.fact_ids}")
            print(f"    Consequence: {o.consequence}")
            if o.coach_action:
                print(f"    For the coach: {o.coach_action}")
            print(f"    Cup match: {o.compare_to_cup}")
        for r in insight.rejected_claims:
            print(f"  ✗ left out: {r.text}\n    reason: {r.reason}")
        if insight.fallback_reason:
            print(f"  fallback: {insight.fallback_reason}")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
