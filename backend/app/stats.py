"""Stats Engine: keeps the running match numbers, one source item at a time.

Incremental on purpose, so the same code works for a replay and a live feed.
After a seek the simulator resets it and applies everything up to the new `t`.
"""
from app.contracts import MatchStats, SourceEvent, SourceFrame
from app.sources import MatchItem


class StatsEngine:
    def __init__(self, home: str, away: str) -> None:
        self.home, self.away = home, away
        self.reset()

    def reset(self) -> None:
        self.score = {self.home: 0, self.away: 0}
        self.xg = {self.home: 0.0, self.away: 0.0}
        self.possession_s = {self.home: 0, self.away: 0}
        self._in_possession: str | None = None

    def apply(self, item: MatchItem) -> None:
        if isinstance(item, SourceFrame):
            self._apply_frame(item)
        else:
            self._apply_event(item)

    def _apply_event(self, e: SourceEvent) -> None:
        if e.type == "goal":
            self.score = {self.home: e.score_home, self.away: e.score_away}
        elif e.type == "shot" and e.team in self.xg:
            self.xg[e.team] += e.details.get("xg") or 0.0

    def _apply_frame(self, f: SourceFrame) -> None:
        # Possession = the team of the last player on the ball, counted while the ball is live
        # (same definition as the generator: a pass in flight still belongs to the passer's team).
        if f.ball.holder_id:
            holder = next((p for p in f.players if p.id == f.ball.holder_id), None)
            if holder:
                self._in_possession = holder.team
        if f.ball.live and self._in_possession in self.possession_s:
            self.possession_s[self._in_possession] += 1

    def snapshot(self) -> MatchStats:
        h, a = self.home, self.away
        total = self.possession_s[h] + self.possession_s[a]
        home_pct = round(100 * self.possession_s[h] / total) if total else 50
        return MatchStats(
            score=(self.score[h], self.score[a]),
            xg=(round(self.xg[h], 2), round(self.xg[a], 2)),
            possession=(home_pct, 100 - home_pct),
        )
