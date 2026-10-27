"""
Data shapes for the agent workflow.

The shapes shared with the Stats Engine and the frontend (Moment, FactSheet, Fact,
MatchSnapshot, Insight, ...) live in app/contracts.py and are re-exported here.
Only the agents' own structured LLM outputs are defined in this module.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.contracts import (
    CorrectionStats,
    Fact,
    FactSheet,
    Insight,
    MatchSnapshot,
    Moment,
    RejectedClaim,
    TeamId,
)

__all__ = [
    "AnalystDraft", "Claim", "CorrectionStats", "Fact", "FactSheet", "Insight",
    "MatchSnapshot", "Moment", "RejectedClaim", "ScoutDraft", "ScoutObservationDraft", "TeamId", "TranslationDraft",
]


class Claim(BaseModel):
    """A single statement the Analyst wants to make, with the facts behind it."""

    text: str = Field(description="One sentence, plain English, at most 30 words")
    fact_ids: list[str] = Field(description="ids of the facts that support this claim, e.g. ['F1','F3']")


class AnalystDraft(BaseModel):
    """Structured output of the Analyst agent."""

    claims: list[Claim] = Field(description="2 or 3 claims, most important first")


class ScoutObservationDraft(BaseModel):
    """One observation of the Scout, before the fact-check."""

    observation: str = Field(description="What happens: structure first, then the change. Numbers only as written in the facts. At most 35 words")
    fact_ids: list[str] = Field(description="ids of the facts it uses, e.g. ['T2','C4']")
    consequence: str = Field(description="What it means for the match. No numbers, no player names. At most 25 words")
    coach_action: str = Field(description="What the opposing staff would adjust, or \"\" when nothing. No numbers, no player names. At most 20 words")
    compare_to_cup: Literal["same", "changed", "n/a"] = Field(description="'changed' or 'same' only when a cited fact gives the cup-match value, else 'n/a'")
    team: str = Field(description="team id the observation is about, e.g. 'ngr'")


class ScoutDraft(BaseModel):
    """Structured output of the Scout agent."""

    observations: list[ScoutObservationDraft] = Field(description="2 or 3 observations, most important first")


class TranslationDraft(BaseModel):
    """Structured output of the Translator agent."""

    texts: list[str] = Field(description="one translation per text, in the same order")
