"""
Runs the agent workflow on the test moments and prints what came out.

    cd backend
    uv run python -m app.agents.run_fixtures                 # model from MODEL_PROVIDER (offline without a token)
    uv run python -m app.agents.run_fixtures --inject-wrong  # the Analyst's first claim gets a wrong number
    uv run python -m app.agents.run_fixtures goal-24 red-53  # only these moments
    uv run python -m app.agents.run_fixtures --json out.json # also write the Insights as JSON (camelCase)
    uv run python -m app.agents.run_fixtures --provider foundry-agents
    uv run python -m app.agents.run_fixtures --compare foundry,foundry-agents   # side by side
    uv run python -m app.agents.run_fixtures --deadline 30   # no fallback on time: see the real latency

Settings in backend/.env.foundry-agents (written by tools/create_foundry_agents.py)
are loaded automatically; variables already set in your shell win.

Exit code 1 if any moment ended in fallback (useful in CI).
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
import re
import sys
import time

from .llm import ModelClient, model_from_env
from .models import AnalystDraft, FactSheet, Insight
from .workflow import run_workflow

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FIXTURES = os.path.join(ROOT, "fixtures", "moments")
ENV_FILES = [os.path.join(ROOT, "backend", ".env"), os.path.join(ROOT, "backend", ".env.foundry-agents")]


def load_env_files() -> None:
    for path in ENV_FILES:
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() != "MODEL_PROVIDER":  # the provider is chosen per run
                    os.environ.setdefault(k.strip(), v.strip())


class WrongNumberModel:
    """Wraps a model and corrupts one number in the Analyst's first claim."""

    def __init__(self, inner: ModelClient):
        self.inner = inner
        self.name = f"{inner.name}+wrong"

    async def draft(self, sheet, prompt):
        draft, tokens = await self.inner.draft(sheet, prompt)
        if draft.claims:
            c = draft.claims[0]
            m = re.search(r"\d+(?:\.\d+)?", c.text)
            if m:
                n = float(m.group())
                bad = f"{n + 0.27:.2f}" if "." in m.group() else str(int(n) + 3)
                c.text = c.text[: m.start()] + bad + c.text[m.end():]
            else:
                c.text = c.text.rstrip(".") + ", his 17th of the season."
        return AnalystDraft(claims=draft.claims), tokens

    def narrate(self, sheet, claims, prompt):
        return self.inner.narrate(sheet, claims, prompt)


def load(ids: list[str]) -> list[FactSheet]:
    paths = sorted(glob.glob(os.path.join(FIXTURES, "*.json")))
    sheets = [FactSheet.model_validate(json.load(open(p, encoding="utf-8"))) for p in paths]
    sheets.sort(key=lambda s: s.moment.t)
    return [s for s in sheets if not ids or s.moment.moment_id in ids]


def percentile(values: list[int], q: float) -> int:
    v = sorted(values)
    return v[min(len(v) - 1, int(len(v) * q))] if v else 0


async def run_all(model: ModelClient, sheets: list[FactSheet], verbose: bool, deadline_s: float | None = None) -> list[Insight]:
    results = []
    for sheet in sheets:
        phases: list[str] = []
        first_text_ms: list[int] = []
        t0 = time.perf_counter()

        def on_update(i: Insight) -> None:
            phases.append(i.phase)
            if i.phase == "streaming" and not first_text_ms:
                first_text_ms.append(round((time.perf_counter() - t0) * 1000))

        insight = await run_workflow(sheet.moment, sheet, on_update, model=model, deadline_s=deadline_s)
        insight.__dict__["first_text_ms"] = first_text_ms[0] if first_text_ms else None
        results.append(insight)
        if verbose:
            flow = " → ".join(dict.fromkeys(phases))
            print(f"■ {sheet.moment.minute:>5}'  {sheet.moment.moment_id:<12} {insight.status.upper():<9} {insight.latency_ms} ms"
                  + (f" · first text {first_text_ms[0]} ms" if first_text_ms else "")
                  + (f" · {insight.tokens} tokens" if insight.tokens else "") + f"   [{flow}]")
            print(f"   {insight.text}")
            if insight.evidence:
                print("   evidence: " + " | ".join(insight.evidence))
            for r in insight.rejected_claims:
                print(f"   ✗ rejected: {r.text}\n     reason: {r.reason}")
            if insight.fallback_reason:
                print(f"   fallback: {insight.fallback_reason}")
            print()
    return results


def summary(name: str, results: list[Insight]) -> str:
    lat = [i.latency_ms or 0 for i in results]
    first = [i.__dict__.get("first_text_ms") for i in results if i.__dict__.get("first_text_ms")]
    counts = {s: sum(i.status == s for i in results) for s in ("checked", "corrected", "fallback")}
    tokens = sum(i.tokens or 0 for i in results)
    return (f"{name:<15} total p50 {percentile(lat, .5):>5} ms · p95 {percentile(lat, .95):>5} ms · "
            f"first text p50 {percentile(first, .5):>5} ms · checked {counts['checked']}, corrected {counts['corrected']}, "
            f"fallback {counts['fallback']}" + (f" · {tokens} tokens" if tokens else ""))


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="moment ids, e.g. goal-24")
    ap.add_argument("--provider", help="github, foundry, foundry-agents or offline (default: MODEL_PROVIDER)")
    ap.add_argument("--compare", help="comma-separated providers to run side by side, e.g. foundry,foundry-agents")
    ap.add_argument("--inject-wrong", action="store_true", help="corrupt a number in the first claim")
    ap.add_argument("--json", help="write the Insights to this file")
    ap.add_argument("--deadline", type=float, help="seconds before fallback (default AGENT_DEADLINE_S or 6); raise it to see the real latency")
    args = ap.parse_args()
    load_env_files()

    sheets = load(args.ids)
    if not sheets:
        print(f"No moments found in {FIXTURES}. Run tools/build_test_moments.py first.")
        return 2

    providers = [p.strip() for p in args.compare.split(",")] if args.compare else [args.provider]
    all_results: dict[str, list[Insight]] = {}
    for provider in providers:
        model: ModelClient = model_from_env(provider)
        if args.inject_wrong:
            model = WrongNumberModel(model)
        warmup = getattr(getattr(model, "inner", model), "warmup", None)
        if warmup:
            t_w = time.perf_counter()
            await warmup()
            print(f"Login token ready in {time.perf_counter() - t_w:.1f} s (not counted in the latencies)")
        print(f"Model: {model.name} · {len(sheets)} moments\n")
        t0 = time.perf_counter()
        results = await run_all(model, sheets, verbose=True, deadline_s=args.deadline)
        all_results[model.name] = results
        print(f"Done in {time.perf_counter() - t0:.1f} s\n")

    if len(all_results) > 1:
        names = list(all_results)
        print("=" * 100)
        print("Comparison\n")
        for name in names:
            print(summary(name, all_results[name]))
        print()
        for k, sheet in enumerate(sheets):
            print(f"■ {sheet.moment.minute}' {sheet.moment.moment_id}")
            for name in names:
                i = all_results[name][k]
                print(f"   {name:<15} {i.status:<9} {i.latency_ms:>5} ms  {i.text}")
            print()
    else:
        name, results = next(iter(all_results.items()))
        print(summary(name, results))

    if args.json:
        payload = {name: [i.to_json() for i in res] for name, res in all_results.items()}
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload if len(payload) > 1 else next(iter(payload.values())), f, indent=1, ensure_ascii=False)
        print(f"Wrote {args.json}")
    return 1 if any(i.status == "fallback" for res in all_results.values() for i in res) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
