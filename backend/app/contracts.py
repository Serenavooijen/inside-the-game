"""Shared data contracts, v0.3. The single place for every shape the backend uses.

Three layers:

1. Wire: what goes to the frontend over SSE and from GET /state. Mirrors
   frontend/lib/contracts.ts field for field; change both together.
2. Agents: what the Stats Engine hands to run_workflow (FactSheet) and what
   comes back (Insight, also sent on the wire).
3. Source: what a MatchSource delivers (raw events and tracking). Backend-internal;
   the Stats Engine and Moment Detector turn it into layers 1 and 2.

Conventions:
- Python is snake_case, JSON is camelCase. Serialise with `.to_json()`.
- `t` is match time in seconds since kick-off, continuous over all periods
  (= the generator's `frame`). A float, so real feeds can be sub-second.
- Positions are absolute pitch metres: x 0..105, y 0..68.
- `generation` increases on every load and seek; anything older is dropped.
- Team ids are plain strings ("kba", "ngr"), so a new match needs no code change.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

TeamId = str                        # from the match data, e.g. "kba"; every match brings its own teams
Mode = Literal["live", "replay"]
Speed = Literal[1, 10]
Period = Literal[1, 2, 3, 4, 5]     # 3, 4 = extra time, 5 = penalty shoot-out


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    def to_json(self) -> dict[str, Any]:
        """camelCase, without empty optional fields (the frontend treats them as absent)."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


# ============================================================================ 1. wire

class Point(CamelModel):
    x: float
    y: float


class Player(CamelModel):
    id: str
    team: TeamId
    n: int                          # shirt number
    x: float
    y: float
    gk: bool | None = None
    name: str | None = None


class Frame(CamelModel):
    t: float
    players: list[Player]
    ball: Point


OverlaySlot = Literal["tag", "pass", "shot", "sprint"]


class Overlay(CamelModel):
    """Fast lane: deterministic, no LLM. The frontend shows at most one per slot."""
    id: str
    t: float
    slot: OverlaySlot
    player_id: str
    value: float | None = None      # pass: quality 0-1 · shot: xG · sprint: peak km/h
    to: Point | None = None         # pass target or shot target
    from_: Point | None = Field(default=None, alias="from")  # sprint: start of the run
    generation: int = 0


MatchEventKind = Literal["goal", "yellow", "red", "sub", "bigchance"]


class MatchEvent(CamelModel):
    """A key event for the scorebar and timeline (not every pass: see SourceEvent)."""
    id: str
    t: float
    minute: str                     # "24", "45+2"
    kind: MatchEventKind
    team: TeamId
    player_id: str | None = None
    text: str                       # "Okafor 67'"
    detail: str | None = None       # "Okafor (19) · assist Lindqvist (21)"
    key: bool | None = None         # key moment: slow to 1x and show the hero card


InsightType = Literal["goal", "bigchance", "card", "momentum", "update", "fulltime"]
InsightStatus = Literal["checked", "corrected", "fallback"]
InsightPhase = Literal["analysing", "streaming", "done"]


class Zone(CamelModel):
    """Area highlighted on the mini pitch."""
    x: float
    y: float
    w: float
    h: float
    label: str
    line: float | None = None       # dashed line at this x, e.g. the defensive line
    dir: Literal[1, -1] | None = None


class CorrectionStats(CamelModel):
    a: str
    a_label: str
    a_team: TeamId
    b: str
    b_label: str
    b_team: TeamId


class RejectedClaim(CamelModel):
    text: str
    reason: str
    fact_ids: list[str] = []


class Insight(CamelModel):
    """Smart lane: output of run_workflow, sent as SSE `insight` (updated by id)."""
    id: str
    t: float
    minute: str
    moment_id: str | None = None
    type: InsightType
    card: Literal["yellow", "red"] | None = None
    team: TeamId | None = None
    text: str                       # grows while phase = "streaming"
    status: InsightStatus = "checked"
    phase: InsightPhase = "done"
    evidence: list[str] = []
    zone: Zone | None = None
    claim: str | None = None        # status "corrected": the draft claim that failed the check
    stats: CorrectionStats | None = None
    analyst_stats: list[dict[str, str]] | None = None
    fallback_reason: str | None = None
    generation: int = 0
    # Traceability (not shown in the UI yet)
    cited_fact_ids: list[str] = []
    rejected_claims: list[RejectedClaim] = []
    latency_ms: int | None = None
    tokens: int | None = None


class MatchStats(CamelModel):
    score: tuple[int, int]
    xg: tuple[float, float]
    possession: tuple[float, float]


class Tick(CamelModel):
    """Sent for every new match second."""
    t: float
    period: Period
    clock: str                      # "57:40", "45+1:30"
    minute: str                     # "58", "45+2"
    speed: Speed
    playing: bool
    generation: int
    frame: Frame
    stats: MatchStats
    key_moment_id: str | None = None  # set while a key moment is on screen (slowed to 1x)
    finished: bool = False


class Marker(CamelModel):
    t: float
    minute: str
    kind: Literal["goal", "card", "red", "corrected"]
    team: TeamId | None = None
    title: str


class MatchState(Tick):
    """Full picture, sent on (re)connect and from GET /state."""
    match_id: str
    mode: Mode
    duration: float                 # t at full time
    halftime: float                 # first t of the second half
    events: list[MatchEvent] = []
    insights: list[Insight] = []
    markers: list[Marker] | None = None  # replay only


class TeamInfo(CamelModel):
    id: str
    name: str
    short: str
    color: str
    fg: str


class MatchSummary(CamelModel):
    """Entry in GET /matches."""
    id: str
    home: TeamInfo
    away: TeamInfo
    score: str
    story: str
    meta: str
    available: bool


# GET /stream sends `event: <name>` + `data: <payload.to_json()>`.
SseEventName = Literal["tick", "overlay", "event", "insight", "state"]


# Request bodies keep snake_case keys, as the frontend sends them.
class LoadRequest(BaseModel):
    match_id: str
    mode: Mode = "replay"


class SpeedRequest(BaseModel):
    factor: Speed


class SeekRequest(BaseModel):
    t: float = Field(ge=0)          # live: must be <= the latest t received


# ============================================================================ 2. agents

class Fact(CamelModel):
    """One verifiable statement, computed by the Stats Engine (code, not an LLM).

    Put derived numbers in `text` itself ("4 minutes before this goal"): the checker
    only accepts numbers that literally appear in a cited fact.
    """
    fact_id: str                    # "F1", "F2", ... most important first
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


class MatchSnapshot(CamelModel):
    """Score and key numbers at the moment, (home, away). Serialised as `matchState`."""
    score: tuple[int, int]
    players_on_pitch: tuple[int, int] = (11, 11)
    possession: tuple[float, float]
    xg: tuple[float, float]
    shots: tuple[int, int]


class FactSheet(CamelModel):
    """Input for run_workflow: 3-6 facts about one moment."""
    moment: Moment
    match_state: MatchSnapshot
    facts: list[Fact]
    home: TeamId                    # match_state tuples are (home, away)
    away: TeamId
    team_names: dict[TeamId, str]   # display name per team id, e.g. {"kba": "Kingsbridge"}

    @model_validator(mode="after")
    def _teams_have_names(self) -> FactSheet:
        missing = {self.home, self.away} - self.team_names.keys()
        if missing:
            raise ValueError(f"team_names has no name for {sorted(missing)}")
        return self

    @property
    def home_away(self) -> tuple[str, str]:
        """Display names (home, away), in the order of the match_state tuples."""
        return self.team_names[self.home], self.team_names[self.away]

    def fact(self, fact_id: str) -> Fact | None:
        return next((f for f in self.facts if f.fact_id == fact_id), None)


# ============================================================================ 3. source

SourceEventType = Literal[
    "ball_receipt", "ball_recovery", "block", "clearance", "corner", "cross",
    "dispossessed", "foul", "foul_won", "free_kick", "goal", "goal_kick",
    "interception", "kickoff", "offside", "out_of_play", "pass", "period_end",
    "period_start", "pressure", "red_card", "save", "shot", "simulation",
    "stoppage", "substitution", "tackle", "tactical_change", "take_on",
    "throw_in", "yellow_card",
    "other",                        # unknown provider type; original in details["provider_type"]
]


class SourceEvent(BaseModel):
    """One raw event from a MatchSource (generator now, a real feed later).

    Common fields are typed; type- and source-specific fields (xg, receiver_id,
    reason, scripted, provider ids, ...) live in `details`.
    """
    event_id: int                   # assigned by the source, ascending; provider id in details["provider_event_id"]
    t: float
    period: Period
    second_in_period: float
    clock: str
    minute: str
    type: SourceEventType
    team: str | None = None         # source team code, e.g. "KBA"
    player_id: str | None = None
    player_name: str | None = None
    x: float | None = None
    y: float | None = None
    end_x: float | None = None
    end_y: float | None = None
    outcome: str | None = None
    possession_seq: int | None = None
    score_home: int
    score_away: int
    details: dict[str, Any] = Field(default_factory=dict)


class SourcePlayer(BaseModel):
    id: str
    team: str
    role: str                       # "GK", "RB", ...
    x: float
    y: float
    speed: float                    # m/s


class SourceBall(BaseModel):
    x: float
    y: float
    live: bool
    holder_id: str | None = None


class SourceFrame(BaseModel):
    """Positions of everyone on the pitch at second `t`, as the source delivers them."""
    t: float
    period: Period
    clock: str
    players: list[SourcePlayer]
    ball: SourceBall


class MatchInfo(BaseModel):
    """What a MatchSource knows about its match."""
    match_id: str
    title: str
    home: str
    away: str
    mode: Mode = "replay"
    duration_s: float | None = None # None while a live match is still running

