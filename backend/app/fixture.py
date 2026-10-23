"""MatchSource for the synthetic reference match: the output of generator/generate_match.py.

Reads output/events.json, output/tracking.csv and script/match_script.json once and
serves them as SourceEvent and SourceFrame. Paths can be overridden with
ITG_OUTPUT_DIR and ITG_SCRIPT_DIR (e.g. in Docker).
"""
import csv
import json
import os
from collections import defaultdict
from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path

from app.contracts import (
    MatchInfo, MatchSummary, Mode, SourceBall, SourceEvent, SourceFrame, SourcePlayer, TeamInfo,
)
from app.sources import MatchItem, PlayerInfo

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = Path(os.environ.get("ITG_OUTPUT_DIR", ROOT / "output"))
SCRIPT_DIR = Path(os.environ.get("ITG_SCRIPT_DIR", ROOT / "script"))

MATCH_ID = "kba-ngr"
SUMMARY = MatchSummary(
    id=MATCH_ID,
    home=TeamInfo(id="kba", name="Kingsbridge Athletic", short="KBA", color="#2F6BFF", fg="#FFFFFF"),
    away=TeamInfo(id="ngr", name="Northgate Rovers", short="NGR", color="#FFB400", fg="#121212"),
    score="2–2",
    story="Kingsbridge had the ball and the xG (2.48 – 1.52), then lost Brannigan to a second yellow. "
          "Northgate led twice; a substitute’s header made it 2-2.",
    meta="4-3-3 vs 4-4-2 · 4 goals · 1 red card · 1 claim corrected",
    available=True,
)

_COMMON = set(SourceEvent.model_fields) - {"t", "details"}


def to_source_event(row: dict) -> SourceEvent:
    """One row of the generator's events.json; `frame` becomes `t`, the rest goes to details."""
    details = {k: v for k, v in row.items() if k not in _COMMON and k != "frame" and v is not None}
    common = {k: v for k, v in row.items() if k in _COMMON}
    return SourceEvent(t=row["frame"], details=details, **common)


def _read_frames(path: Path) -> list[SourceFrame]:
    rows: dict[int, list[dict]] = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[int(r["frame"])].append(r)
    frames = []
    for t in sorted(rows):
        group = rows[t]
        ball = next(r for r in group if r["object_id"] == "ball")
        frames.append(SourceFrame(
            t=t, period=int(ball["period"]), clock=ball["clock"],
            players=[
                SourcePlayer(id=r["object_id"], team=r["team"], role=r["role_or_state"],
                             x=float(r["x"]), y=float(r["y"]), speed=float(r["speed_ms_or_ball_holder"] or 0))
                for r in group if r["object_id"] != "ball"
            ],
            ball=SourceBall(x=float(ball["x"]), y=float(ball["y"]), live=ball["role_or_state"] == "live",
                            holder_id=ball["speed_ms_or_ball_holder"] or None),
        ))
    return frames


@lru_cache(maxsize=1)
def _load() -> tuple[MatchInfo, dict[str, PlayerInfo], list[MatchItem]]:
    script = json.loads((SCRIPT_DIR / "match_script.json").read_text(encoding="utf-8"))
    rows = json.loads((OUTPUT_DIR / "events.json").read_text(encoding="utf-8"))
    frames = _read_frames(OUTPUT_DIR / "tracking.csv")

    home, away = script["teams"]["home"], script["teams"]["away"]
    roster = {}
    for team in (home, away):
        for p in team["players"]:
            first, *rest = p["name"].split(" ")
            roster[p["id"]] = PlayerInfo(
                id=p["id"], team=team["id"], n=p["no"], gk=p["pos"] == "GK",
                name=f"{first[0]}. {' '.join(rest)}" if rest else p["name"],
                surname=" ".join(rest) or p["name"],
            )
    info = MatchInfo(match_id=MATCH_ID, title=script["meta"]["title"], home=home["id"], away=away["id"],
                     team_names={t["id"]: t["short"] for t in (home, away)},
                     mode="replay", duration_s=frames[-1].t)
    # Frame before the events of the same second: events then see the positions they happened in.
    items: list[MatchItem] = sorted([*frames, *(to_source_event(r) for r in rows)],
                                    key=lambda i: (i.t, isinstance(i, SourceEvent)))
    return info, roster, items


class GeneratorSource:
    """Replays the generated match. Everything is in memory; the simulator does the pacing."""

    def __init__(self) -> None:
        self.info, self.roster, self._items = _load()

    @property
    def mode(self) -> Mode:
        return "replay"

    async def items(self, from_t: float = 0.0) -> AsyncIterator[MatchItem]:
        for item in self._items:
            if item.t >= from_t:
                yield item
