"""
Data shapes for the agent workflow.

The shapes shared with the Stats Engine and the frontend (Moment, FactSheet, Fact,
MatchSnapshot, Insight, ...) live in app/contracts.py and are re-exported here.
Only the agents' own structured LLM outputs are defined in this module.
"""

from __future__ import annotations

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
    "MatchSnapshot", "Moment", "RejectedClaim", "TeamId",
]


class Claim(BaseModel):
    """A single statement the Analyst wants to make, with the facts behind it."""

    text: str = Field(description="One sentence, plain English, at most 30 words")
    fact_ids: list[str] = Field(description="ids of the facts that support this claim, e.g. ['F1','F3']")


class AnalystDraft(BaseModel):
    """Structured output of the Analyst agent."""

    claims: list[Claim] = Field(description="2 or 3 claims, most important first")
