"""Instructions and prompt builders for the agents. Keep prompts short: every token is latency."""

from __future__ import annotations

from .models import Claim, FactSheet

ANALYST_INSTRUCTIONS = """You are the Analyst in a live football broadcast team.
You receive one match moment and a numbered list of facts computed from the event data.
Pick the 2 or 3 facts that best explain WHY this moment matters (cause, pattern, consequence),
and write each as one short claim.

Rules:
- Use only the facts given. Never invent players, numbers, minutes or events.
- Every claim cites the fact ids it uses, e.g. ["F2","F5"].
- Copy numbers exactly as they appear in the facts. Do not calculate new ones
  (no differences, totals, counts or roundings): if a number is not written in a fact, leave it out.
- Plain English, at most 30 words per claim. No hedging, no hype."""

NARRATOR_INSTRUCTIONS = """You are the Narrator: you turn checked claims into what a TV analyst would say.
Write 1 to 3 sentences, at most 55 words in total, for a football fan watching live.
Use only the claims you are given. You may rephrase and connect them, nothing more:
- no numbers, names, roles (goalkeeper, captain, substitute) or places (inside the box) that are not in the claims;
- do not change who did what;
- no predictions or judgements the claims do not make ("turning point", "will disrupt").
Write numbers as digits. No greeting, no hashtags, no emoji. Start with the point."""


def analyst_prompt(sheet: FactSheet) -> str:
    s = sheet.match_state
    home, away = sheet.home_away
    lines = [
        f"Moment ({sheet.moment.minute}'): {sheet.moment.headline}",
        f"Score: {home} {s.score[0]}-{s.score[1]} {away} · players on the pitch {s.players_on_pitch[0]} v {s.players_on_pitch[1]}",
        "Facts:",
    ]
    for f in sheet.facts:
        lines.append(f"[{f.fact_id}] {f.text}")
    return "\n".join(lines)


def narrator_prompt(sheet: FactSheet, claims: list[Claim]) -> str:
    lines = [f"Moment ({sheet.moment.minute}'): {sheet.moment.headline}", "Checked claims:"]
    lines += [f"- {c.text}" for c in claims]
    return "\n".join(lines)
