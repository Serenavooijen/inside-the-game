"""
Puts real agent output into the recorded match, so the mock backend plays it.

    cd backend
    uv run python -m app.agents.run_fixtures --provider foundry-agents --json ../frontend/data/agent-insights.json
    cd ../frontend
    uv run --no-project python scripts/merge_agent_insights.py data/agent-insights.json

For every agent Insight, the recorded insight of the same type at (almost) the same
match second is replaced: text, status, evidence and the fact-check trail come from
the agents; the pitch zone and the link to the match event are kept. Run it again
after a new agent run; the original texts are kept in "scriptedText" so nothing is lost.
"""

from __future__ import annotations

import json
import os
import sys

MATCH = os.path.join(os.path.dirname(__file__), "..", "data", "matches", "kba-ngr.json")
FROM_AGENTS = ("text", "status", "evidence", "claim", "rejectedClaims", "citedFactIds", "fallbackReason", "latencyMs", "tokens", "analystStats")


def main(path: str) -> int:
    agent = json.load(open(path, encoding="utf-8"))
    if isinstance(agent, dict):  # --compare output: {provider: [...]}; take the first provider
        agent = next(iter(agent.values()))
    match = json.load(open(MATCH, encoding="utf-8"))
    recorded = match["insights"]

    done = 0
    for a in agent:
        same = [r for r in recorded if r["type"] == a["type"] and abs(r["t"] - a["t"]) <= 10]
        if not same:
            print(f"  ? no recorded insight for {a.get('momentId')} ({a['type']} at t={a['t']}), skipped")
            continue
        r = min(same, key=lambda r: abs(r["t"] - a["t"]))
        r.setdefault("scriptedText", r["text"])
        for k in FROM_AGENTS:
            r.pop(k, None)
            if a.get(k) not in (None, [], ""):
                r[k] = a[k]
        r["source"] = "agents"
        done += 1
        print(f"  ✓ {r['minute']:>5}'  {r['id']:<16} {r['status']:<9} {r['text'][:70]}…")

    json.dump(match, open(MATCH, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"\n{done} of {len(agent)} agent insights merged into {os.path.normpath(MATCH)}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
