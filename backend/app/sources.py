"""Where match data comes from.

Everything downstream (Stats Engine, Moment Detector) only sees SourceEvent and
SourceFrame. A MatchSource is the adapter that turns one kind of
input into those: the synthetic fixture now, a recorded run for replay, and later
a real provider feed or video eventing. Each source converts coordinates, event
types, ids and time to the conventions in contracts.py.
"""
from collections.abc import AsyncIterator
from typing import Protocol

from pydantic import BaseModel

from app.contracts import MatchInfo, Mode, SourceEvent, SourceFrame

MatchItem = SourceEvent | SourceFrame


class PlayerInfo(BaseModel):
    """Squad data a source knows about each player."""
    id: str
    team: str                       # source team code, e.g. "KBA"
    n: int                          # shirt number
    name: str                       # display name, e.g. "T. Ferreira-Lind"
    surname: str
    gk: bool = False


class MatchSource(Protocol):
    info: MatchInfo
    roster: dict[str, PlayerInfo]

    @property
    def mode(self) -> Mode: ...

    def items(self, from_t: float = 0.0) -> AsyncIterator[MatchItem]:
        """Source events and frames in ascending `t`, starting at `from_t`.

        replay: yields everything immediately; the simulator paces it by `t` and speed.
        live:   yields items as they arrive from the feed and never ends before full time.
        """
        ...
