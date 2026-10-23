"""
Data shapes for the agent workflow.

Python uses snake_case; JSON uses camelCase (the frontend contract in
frontend/lib/contracts.ts). Serialise with `model_dump(by_alias=True)`.

The FactSheet side follows Bryan's proposal (Moment, MatchState, Fact with
fact_id and source_event_ids). When backend/app/contracts.py is merged, import
the shared models from there and delete the duplicates here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# Team id from the match data, e.g. "kba". Not a fixed list: every match brings its own teams.
TeamId = str
# 1–2 halves, 3–4 extra time, 5 penalty shoot-out
Period = Literal[1, 2, 3, 4, 5]

# ---------------------------------------------------------------- input: FactSheet


class Fact(CamelModel):
    """One verifiable statement, computed by the Statistician (code, not an LLM)."""

    fact_id: str
    text: str = Field(description="Readable line, e.g. 'Shot xG 0.41'")
    metric: str = Field(description="Machine name, e.g. 'shot_xg'")
    value: float | str
    unit: str | None = None
    window: str | None = Field(default=None, description="Time window, e.g. \"53'–87'\"")
    source_event_ids: list[int] = []


class Moment(CamelModel):
    moment_id: str
    t: float
    minute: str
    kind: Literal["goal", "red_card", "yellow_card", "big_chance", "tactical_change", "update", "full_time"]
    team: TeamId | None = None
    player_id: str | None = None
    headline: str = Field(description="Neutral one-liner from the event data, e.g. 'Goal Northgate: Adeyemi-Clarke (9), assist Duarte (8)'")


class MatchState(CamelModel):
    score: tuple[int, int]
    players_on_pitch: tuple[int, int] = (11, 11)
    possession: tuple[float, float]
    xg: tuple[float, float]
    shots: tuple[int, int]


class FactSheet(CamelModel):
    moment: Moment
    match_state: MatchState
    facts: list[Fact]
    # Display names per team id, home team first (the score and players_on_pitch use the same order).
    team_names: dict[TeamId, str] = {"kba": "Kingsbridge", "ngr": "Northgate"}

    @property
    def home_away(self) -> tuple[str, str]:
        names = list(self.team_names.values())
        return (names[0] if names else "Home", names[1] if len(names) > 1 else "Away")

    def fact(self, fact_id: str) -> Fact | None:
        return next((f for f in self.facts if f.fact_id == fact_id), None)


# ---------------------------------------------------------------- agent outputs


class Claim(BaseModel):
    """A single statement the Analyst wants to make, with the facts behind it."""

    text: str = Field(description="One sentence, plain English, at most 30 words")
    fact_ids: list[str] = Field(description="ids of the facts that support this claim, e.g. ['F1','F3']")


class AnalystDraft(BaseModel):
    """Structured output of the Analyst agent."""

    claims: list[Claim] = Field(description="2 or 3 claims, most important first")


class RejectedClaim(CamelModel):
    text: str
    reason: str
    fact_ids: list[str] = []


# ---------------------------------------------------------------- output: Insight (frontend contract)


class CorrectionStats(CamelModel):
    a: str
    a_label: str
    a_team: TeamId
    b: str
    b_label: str
    b_team: TeamId


class Insight(CamelModel):
    id: str
    t: float
    minute: str
    moment_id: str | None = None
    type: Literal["goal", "bigchance", "card", "momentum", "update", "fulltime"]
    card: Literal["yellow", "red"] | None = None
    team: TeamId | None = None
    text: str
    status: Literal["checked", "corrected", "fallback"] = "checked"
    phase: Literal["analysing", "streaming", "done"] = "done"
    evidence: list[str] = []
    claim: str | None = None
    stats: CorrectionStats | None = None
    analyst_stats: list[dict[str, str]] | None = None
    fallback_reason: str | None = None
    generation: int = 0
    # Traceability (not shown in the UI yet)
    cited_fact_ids: list[str] = []
    rejected_claims: list[RejectedClaim] = []
    latency_ms: int | None = None
    tokens: int | None = None

    def to_json(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)
