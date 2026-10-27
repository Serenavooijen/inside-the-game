"""Instructions and prompt builders for the agents. Keep prompts short: every token is latency."""

from __future__ import annotations

from app.contracts import TacticalFactSheet, TacticalObservation

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
- fact_ids: the ids of the facts it uses, at most 3, e.g. ["T2","C4"]. Fact ids start with T or C;
  B1, D1, G2 ... are concept ids, never fact ids.
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
8. One concept per observation. Write in the third person and name the teams; never "we", "us" or "our".
9. For intensity, height and compactness use only the labels written in the facts ("very intense pressing",
   "low block", "compact" ...). Never judge a number yourself.
10. Say something about the score, the game state or the purpose of a substitution only if it matches the
    game-state fact (e.g. "At 61' Northgate were level at 1-1, 11 v 11").
11. When your previous analysis is given: give only new or changed advice for the coach and repeat nothing.
    If the advice for a point would be the same as before, leave coach_action "".

Tone: concrete, tactical, no hype. Example observation: "Northgate's 6 drops between the centre-backs in
most build-up phases, creating a back three; Kingsbridge's two strikers are outnumbered in the first press."
Example consequence: "Kingsbridge cannot press high without leaving the midfield open." """

TRIGGER_LABEL = {"interval": "every 5 minutes", "half_time": "half time", "substitution": "after a substitution",
                 "scouting": "scouting report on the cup match"}


def scout_prompt(sheet: TacticalFactSheet, previous: list[TacticalObservation] | None = None) -> str:
    """Only the one-line definitions of the concepts whose detector fired, never the whole playbook.
    `previous`: the Scout's last checked analysis, so it gives only new or changed advice."""
    from .playbook import concepts, one_liner

    home, away = sheet.team_names[sheet.home], sheet.team_names[sheet.away]
    lines = [f"Window {sheet.window.label} ({TRIGGER_LABEL.get(sheet.trigger, sheet.trigger)}): {sheet.headline}",
             f"Team ids: {sheet.home} = {home}, {sheet.away} = {away}"]
    if sheet.trigger == "scouting":
        lines.append("This is the scouting report on the cup match itself, written before today's kick-off. "
                     "Describe how each team played in the cup match: their plan and what changed during it. "
                     "There is no live match yet: never compare, and use compare_to_cup \"n/a\". "
                     "Only describe what a team clearly did; a low percentage means the team did not do it.")
    if sheet.trigger == "substitution":
        lines.append("This is the impact of a substitution, about 8 minutes after it. Answer: did the change work and "
                     "what changed for the team; how did the opponent react. Keep the order structure, change, "
                     "consequence, coach response. Facts about the period after the change describe that period only.")
    if sheet.match_state:
        s = sheet.match_state
        lines.append(f"Score: {home} {s.score[0]}-{s.score[1]} {away} · players on the pitch {s.players_on_pitch[0]} v {s.players_on_pitch[1]}")
    lines.append("Concepts found:")
    # Names only: concept ids ("P1") look like fact ids ("T1") and got cited as such.
    lines += [f"- {one_liner(c).split(' ', 1)[1]}" for c in sheet.concepts_fired if one_liner(c)]
    lines.append("Facts:")
    name = lambda c: concepts()[c].name if c in concepts() else "game state"
    lines += [f"[{f.fact_id}] {f.text} (team {f.team}; {name(f.concept)})" for f in sheet.facts]
    if sheet.baseline:
        lines.append("Cup-match baseline:")
        lines += [f"[{f.fact_id}] {f.text} (team {f.team}; {name(f.concept)})" for f in sheet.baseline]
    if previous:
        lines.append("Your previous analysis (context only: do not cite it, do not repeat its advice):")
        lines += [f"- {o.observation} Advice: {o.coach_action or '-'}" for o in previous]
    return "\n".join(lines)


TRANSLATOR_INSTRUCTIONS = """You are the Translator of a live football broadcast. The texts you get have been
fact-checked in English; your translation is checked again against them.

Translate every text into the language asked, literally and naturally, as a football commentator would say it:
- add nothing and leave nothing out;
- write every number as digits, exactly as in the English text (the decimal comma is fine: 0.41 -> 0,41);
  keep notations such as 1v1, 4-4-2, 2-3-2-3, 1-0 and 24' exactly as they are;
- keep the names of players, clubs and places exactly as they are: never translate or adapt a name;
- keep football terms that fans use in that language (xG, VAR).
Return one translation per text, in the same order. No notes, no quotes around the texts."""

LANGUAGE_NAMES = {"nl": "Dutch", "es": "Spanish", "fr": "French", "de": "German", "it": "Italian", "pt": "Portuguese"}


def translator_prompt(lang: str, texts: list[str]) -> str:
    lines = [f"Translate into {LANGUAGE_NAMES.get(lang, lang)} ({lang}). {len(texts)} text(s):"]
    lines += [f"[{i + 1}] {t}" for i, t in enumerate(texts)]
    return "\n".join(lines)
