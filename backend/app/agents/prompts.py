"""Instructions and prompt builders for the agents. Keep prompts short: every token is latency."""

from __future__ import annotations

from app.contracts import TacticalFactSheet

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


SCOUT_INSTRUCTIONS = """You are the Scout: an opposition analyst writing for the coaching staff during a live match.
You receive tactical facts computed from tracking data for one window of play, the playbook concepts
whose detectors fired, and baseline facts from the previous meeting of these teams (the cup match).

Write 2 or 3 observations, most important first. Each has:
- observation: what happens on the pitch. Start with the structure (build-up, lines, flanks, press),
  then what changed. Use numbers only exactly as written in the facts. At most 35 words.
- fact_ids: the ids of the facts it uses, e.g. ["T2","C4"].
- consequence: what this means for the match. No numbers and no player names. At most 25 words.
- coach_action: what the opposing staff would adjust, or "" when nothing. No numbers, no player names. At most 20 words.
- compare_to_cup: "changed" when a cited fact gives a different cup-match value, "same" when it gives
  the same plan, "n/a" when no cited fact mentions the cup match.
- team: the id of the team the observation is about.

Rules:
1. Name a concept only if it is in the list of concepts found, and cite its facts.
2. Use the concept names in plain English and explain them in one clause for fans,
   e.g. "a back three in build-up, because the 6 drops in".
3. Order each observation as structure, change, consequence, coach response.
4. Consequence and coach response contain no new numbers and no new names.
5. Prefer what changed (against the previous window or the cup match) over what stayed the same.
6. 2-3 observations. Quality over coverage.
7. Never invent players, numbers, minutes or events. Do not calculate new numbers.

Tone: concrete, tactical, no hype. Example observation: "Northgate's 6 drops between the centre-backs in
most build-up phases, creating a back three; Kingsbridge's two strikers are outnumbered in the first press."
Example consequence: "Kingsbridge cannot press high without leaving the midfield open." """

TRIGGER_LABEL = {"interval": "every 5 minutes", "half_time": "half time", "substitution": "after a substitution",
                 "scouting": "scouting report on the cup match"}


def scout_prompt(sheet: TacticalFactSheet) -> str:
    """Only the one-line definitions of the concepts whose detector fired, never the whole playbook."""
    from .playbook import one_liner

    home, away = sheet.team_names[sheet.home], sheet.team_names[sheet.away]
    lines = [f"Window {sheet.window.label} ({TRIGGER_LABEL.get(sheet.trigger, sheet.trigger)}): {sheet.headline}",
             f"Team ids: {sheet.home} = {home}, {sheet.away} = {away}"]
    if sheet.match_state:
        s = sheet.match_state
        lines.append(f"Score: {home} {s.score[0]}-{s.score[1]} {away} · players on the pitch {s.players_on_pitch[0]} v {s.players_on_pitch[1]}")
    lines.append("Concepts found:")
    lines += [f"- {one_liner(c)}" for c in sheet.concepts_fired if one_liner(c)]
    lines.append("Facts:")
    lines += [f"[{f.fact_id}] ({f.team}, {f.concept}) {f.text}" for f in sheet.facts]
    if sheet.baseline:
        lines.append("Cup-match baseline:")
        lines += [f"[{f.fact_id}] ({f.team}, {f.concept}) {f.text}" for f in sheet.baseline]
    return "\n".join(lines)
