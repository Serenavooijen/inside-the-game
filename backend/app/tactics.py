"""Tactician: the tactical fingerprint of both teams per window (code, not an LLM).

Implements the detectors of app/agents/knowledge/tactics_playbook.md on the 1 Hz
tracking and the events. Each detector measures its signals in a window and only
yields a Fact when the signal is meaningful: strong on its own, or changed against
the previous window or the cup baseline. Derived numbers (differences, before and
after) go into the fact text itself, because the checker only accepts numbers that
literally appear in a cited fact.

Only frames and events up to the end of the window are used, so it works the same
during a live match. Everything is plain Python on immutable data; the Scout lane
runs it in a worker thread so the fast lane never waits.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from statistics import mean

from app.contracts import (
    Fact, Heatmap, MatchInfo, MatchSnapshot, Player, SourceEvent, SourceFrame, TacticalFactSheet,
    TacticalTrigger, TacticalWindow,
)
from app.sources import PlayerInfo
from app.wire import minute_from_clock, team_id

L, W = 105.0, 68.0
HALF = 52.5
MIN_FRAMES = 60             # a window needs this many frames of a situation before a detector speaks
MIN_PHASES = 5              # build-up phases needed for B1 / B2 / B6
PHASE_MIN_S = 3             # a build-up phase lasts at least this long
LINE_TOL_M = 6.0            # B1/B2: the 6 is "in the last line" within this x of the centre-backs
LAST_LINE_M = 10.0          # B1: players counted in the last line, within this x of the centre-backs
BESIDE_M = 10.0             # B2: next to a centre-back, at most this far outside the pair
INVERT_Y_M = 14.0           # B3: an inverted full-back is this close to the centre line (y 34)
INVERT_X_M = 10.0           # B3: ... and roughly level with the 6
LONG_M = 35.0               # B5: a long ball
SWITCH_M = 30.0             # P2: lateral distance of a switch of play
PPDA_ZONE_X = 42.0          # D3: the defending team's x beyond which it presses (the opponent's own 60%)
HIGH_X = 70.0               # D3: recoveries in the attacking third
COUNTERPRESS_S = 5          # T1
COUNTER_S = 10              # T3
MOVED_M = 10.0              # G1: a player's mean position moved this far
GRID_COLS, GRID_ROWS = 6, 4  # heatmap
SUB_BEFORE_S = 600          # G2: compare 10 minutes before a substitution with the time since
CORE_STATIC = {"B1", "B2", "B3", "B5", "P1", "D1", "G2", "G3"}  # facts a short window repeats without a change
FULL_BACKS = ("RB", "LB")
ROLE_NAMES = {"RB": "right-back", "LB": "left-back"}


# ============================================================================ tracking, team-relative

@dataclass(frozen=True)
class At:
    """A player in team-relative metres: x 0 = own goal line, small y = the team's right flank."""
    id: str
    role: str
    x: float
    y: float


@dataclass
class FrameRel:
    t: float
    period: int
    clock: str
    live: bool
    poss: str | None                            # source team code in possession (last player on the ball)
    ball: dict[str, tuple[float, float]]        # per team, team-relative
    team: dict[str, list[At]]                   # per team, outfield players and goalkeeper
    abs_: dict[str, list[tuple[str, float, float]]]  # per team, absolute (id, x, y), for heatmaps and the mini pitch


class Track:
    """All frames turned team-relative once; windows are slices by t."""

    def __init__(self, info: MatchInfo, frames: list[SourceFrame]) -> None:
        self.info = info
        self.frames: list[FrameRel] = []
        poss = None
        for f in frames:
            if f.ball.holder_id:
                holder = next((p for p in f.players if p.id == f.ball.holder_id), None)
                if holder:
                    poss = holder.team
            rel_ball, rel_team, abs_team = {}, {}, {}
            for side in (info.home, info.away):
                rel_ball[side] = self.rel(side, f.period, f.ball.x, f.ball.y)
                ps = [p for p in f.players if p.team == side]
                rel_team[side] = [At(p.id, p.role, *self.rel(side, f.period, p.x, p.y)) for p in ps]
                abs_team[side] = [(p.id, p.x, p.y) for p in ps if p.role != "GK"]
            self.frames.append(FrameRel(f.t, f.period, f.clock, f.ball.live, poss, rel_ball, rel_team, abs_team))
        self.ts = [f.t for f in self.frames]

    def attacks_right(self, team: str, period: int) -> bool:
        return (team == self.info.home) == (period in (1, 3))

    def rel(self, team: str, period: int, x: float, y: float) -> tuple[float, float]:
        return (x, y) if self.attacks_right(team, period) else (L - x, W - y)

    def window(self, from_t: float, to_t: float) -> list[FrameRel]:
        """Frames with from_t <= t <= to_t."""
        return self.frames[bisect_left(self.ts, from_t):bisect_right(self.ts, to_t)]


def _clock_minute(clock: str, up: bool) -> str:
    """'60:00' -> '60', '64:59' -> '65' (up), '45+1:30' -> '45+2' (up) or '45+1'."""
    mm, ss = clock.split(":")
    base, _, extra = mm.partition("+")
    n = int(extra or base) + (1 if up and int(ss) > 0 else 0)
    return f"{int(base)}+{n}" if extra else str(n)


def channel(y: float) -> str:
    """Team-relative y to a channel name: small y is the team's right flank."""
    return "right" if y < W / 3 else "left" if y > 2 * W / 3 else "centre"


def third(x: float) -> str:
    return "defensive third" if x < L / 3 else "attacking third" if x > 2 * L / 3 else "middle third"


# ============================================================================ the fingerprint

@dataclass
class Print:
    """Measured signals of one team in one stretch of play. None = not enough data."""
    team: str
    frames: int = 0
    possession: float | None = None
    buildup_frames: int = 0
    phases: int = 0
    dm_id: str | None = None
    dm_between: float | None = None             # B1: % of build-up phases
    dm_beside: float | None = None              # B2: % of build-up phases
    dm_beside_side: str | None = None
    last_line_in_poss: int | None = None        # B1: players in the last line in build-up
    last_line_out_poss: int | None = None       # ... and without the ball
    fb_invert: dict[str, tuple[str, float]] = field(default_factory=dict)  # B3: role -> (player id, % of build-up time)
    long_share: float | None = None             # B5: % of passes from the own half that go long
    buildup_passes: int = 0
    shape: str | None = None                    # B6
    channels: dict[str, float] | None = None    # P1: % of attacking-half possession per channel
    switches: int = 0                           # P2
    switch_ids: list[int] = field(default_factory=list)
    line_m: float | None = None                 # D1: last line, metres from own goal, without the ball
    first_line_m: float | None = None
    depth_m: float | None = None                # D2: deepest to highest outfield player, without the ball
    width_m: float | None = None
    ppda: float | None = None                   # D3
    high_recoveries: int = 0
    high_recovery_ids: list[int] = field(default_factory=list)
    losses: int = 0                             # T1
    regained: float | None = None               # T1: % of losses won back within 5 s
    counters: int = 0                           # T3: recoveries followed by a shot or box entry within 10 s
    counter_shots: int = 0
    counter_ids: list[int] = field(default_factory=list)
    shots: int = 0
    xg: float = 0.0
    mean_pos: dict[str, tuple[float, float]] = field(default_factory=dict)  # player id -> team-relative mean
    shape_pos: dict[str, tuple[float, float]] = field(default_factory=dict)  # ... relative to the team's centroid (G1)


def pct(a: float, n: float) -> float | None:
    return round(100 * a / n) if n else None


def fingerprint(track: Track, team: str, frames: list[FrameRel], events: list[SourceEvent]) -> Print:
    opp = track.info.away if team == track.info.home else track.info.home
    p = Print(team=team, frames=len(frames))
    live = [f for f in frames if f.live and f.poss in (team, opp)]
    own = [f for f in live if f.poss == team]
    out = [f for f in live if f.poss == opp]
    p.possession = pct(len(own), len(live))

    # ---- build-up (B1, B2, B3, B6): own possession, ball in the own half
    build = [f for f in own if f.ball[team][0] < HALF]
    p.buildup_frames = len(build)
    phases: list[list[FrameRel]] = []
    for f in build:
        if phases and f.t - phases[-1][-1].t == 1 and f.period == phases[-1][-1].period:
            phases[-1].append(f)
        else:
            phases.append([f])
    phases = [ph for ph in phases if len(ph) >= PHASE_MIN_S]
    p.phases = len(phases)

    def roles(f: FrameRel) -> dict[str, At]:
        return {a.role: a for a in f.team[team]}

    def dm_status(f: FrameRel) -> str | None:
        r = roles(f)
        if "DM" not in r or "RCB" not in r or "LCB" not in r or "CB" in r:
            return None
        dm, rcb, lcb = r["DM"], r["RCB"], r["LCB"]
        cb_x = (rcb.x + lcb.x) / 2
        lo, hi = sorted((rcb.y, lcb.y))
        if abs(dm.x - cb_x) > LINE_TOL_M:
            return "ahead"
        if lo < dm.y < hi:
            return "between"
        if min(abs(dm.y - lo), abs(dm.y - hi)) <= BESIDE_M:
            return "beside_left" if dm.y > hi else "beside_right"
        return "ahead"

    statuses = []
    for ph in phases:
        c = Counter(s for f in ph if (s := dm_status(f)))
        if c:
            statuses.append(c.most_common(1)[0][0])
    if len(statuses) >= MIN_PHASES:
        p.dm_id = Counter(a.id for f in build for a in f.team[team] if a.role == "DM").most_common(1)[0][0]
        p.dm_between = pct(statuses.count("between"), len(statuses))
        beside = [s for s in statuses if s.startswith("beside")]
        p.dm_beside = pct(len(beside), len(statuses))
        if beside:
            p.dm_beside_side = Counter(beside).most_common(1)[0][0].removeprefix("beside_")

    def last_line(f: FrameRel) -> int | None:
        r = roles(f)
        cbs = [r[k] for k in ("RCB", "CB", "LCB") if k in r]
        if len(cbs) < 2:
            return None
        cb_x = mean(c.x for c in cbs)
        return sum(1 for a in f.team[team] if a.role != "GK" and a.x <= cb_x + LAST_LINE_M)

    if len(build) >= MIN_FRAMES:
        counts = [n for f in build if (n := last_line(f))]
        p.last_line_in_poss = round(mean(counts)) if counts else None
    if len(out) >= MIN_FRAMES:
        counts = [n for f in out if (n := last_line(f))]
        p.last_line_out_poss = round(mean(counts)) if counts else None

    if len(build) >= MIN_FRAMES:
        for fb in FULL_BACKS:
            hits = n = 0
            who: Counter[str] = Counter()
            for f in build:
                r = roles(f)
                if fb not in r:
                    continue
                n += 1
                level = abs(r[fb].x - r["DM"].x) <= INVERT_X_M if "DM" in r else True
                inside = abs(r[fb].y - W / 2) <= INVERT_Y_M and level
                hits += inside
                who[r[fb].id] += 1 + 10 * inside      # name the player who did it most
            if n >= MIN_FRAMES and who:
                p.fb_invert[fb] = (who.most_common(1)[0][0], pct(hits, n))

    # B6: lines of the mean outfield positions in build-up
    if len(phases) >= MIN_PHASES:
        pos = _mean_positions(team, build)
        xs = sorted(x for pid, (x, _) in pos.items() if _role_in(build, team, pid) != "GK")
        if len(xs) >= 8:
            p.shape = shape_of(xs)

    # ---- in possession: channels (P1)
    attack = [f for f in own if f.ball[team][0] >= HALF]
    if len(attack) >= MIN_FRAMES:
        c = Counter(channel(f.ball[team][1]) for f in attack)
        p.channels = {k: pct(c[k], len(attack)) for k in ("left", "centre", "right")}

    # ---- without the ball: block (D1, D2)
    if len(out) >= MIN_FRAMES:
        lines, firsts, depths, widths = [], [], [], []
        for f in out:
            field_ = [a for a in f.team[team] if a.role != "GK"]
            if len(field_) < 8:
                continue
            xs = sorted(a.x for a in field_)
            ys = [a.y for a in field_]
            lines.append(mean(xs[:4]))
            firsts.append(mean(xs[-2:]))
            depths.append(xs[-1] - xs[0])
            widths.append(max(ys) - min(ys))
        if lines:
            p.line_m, p.first_line_m = round(mean(lines)), round(mean(firsts))
            p.depth_m, p.width_m = round(mean(depths)), round(mean(widths))

    # ---- events: B5, P2, D3, T3
    def rel_ev(e: SourceEvent, x: float, y: float) -> tuple[float, float]:
        return track.rel(team, e.period, x, y)

    passes = [e for e in events if e.team == team and e.type == "pass" and e.x is not None and e.end_x is not None]
    from_own = [e for e in passes if rel_ev(e, e.x, e.y)[0] < HALF]
    p.buildup_passes = len(from_own)
    if len(from_own) >= 8:
        long_ = [e for e in from_own
                 if ((e.details.get("length_m") or 0) > LONG_M or e.details.get("pass_type") == "long_pass")
                 and rel_ev(e, e.end_x, e.end_y)[0] - rel_ev(e, e.x, e.y)[0] > 15]
        p.long_share = pct(len(long_), len(from_own))
    sw = [e for e in passes if abs(e.end_y - e.y) > SWITCH_M and e.outcome == "complete"]
    p.switches, p.switch_ids = len(sw), [e.event_id for e in sw]

    opp_passes = [e for e in events if e.team == opp and e.type == "pass" and e.x is not None
                  and track.rel(opp, e.period, e.x, e.y)[0] < L - PPDA_ZONE_X]
    actions = [e for e in events if e.team == team and e.x is not None
               and (e.type in ("interception", "foul", "block") or (e.type == "tackle" and e.outcome == "won"))
               and rel_ev(e, e.x, e.y)[0] > PPDA_ZONE_X]
    if len(opp_passes) >= 8 and actions:
        p.ppda = round(len(opp_passes) / len(actions), 1)
    high = [e for e in events if e.team == team and e.x is not None
            and e.type in ("ball_recovery", "interception") and rel_ev(e, e.x, e.y)[0] > HIGH_X]
    p.high_recoveries, p.high_recovery_ids = len(high), [e.event_id for e in high]

    shots = [e for e in events if e.team == team and e.type == "shot"]
    p.shots, p.xg = len(shots), round(sum(e.details.get("xg") or 0 for e in shots), 2)

    # ---- transitions from the frames (T1, T3)
    regained = 0
    for i in range(1, len(live)):
        a, b = live[i - 1], live[i]
        if a.poss == team and b.poss == opp and b.t - a.t <= 2:
            p.losses += 1
            back = next((f for f in live[i:i + COUNTERPRESS_S + 2] if f.poss == team), None)
            regained += bool(back and back.t - b.t <= COUNTERPRESS_S)
        elif a.poss == opp and b.poss == team and b.t - a.t <= 2:
            t0 = b.t
            shot = next((e for e in shots if t0 < e.t <= t0 + COUNTER_S), None)
            box = any(f.poss == team and f.ball[team][0] > L - 16.5 and abs(f.ball[team][1] - W / 2) < 20.16
                      for f in live[i:i + COUNTER_S + 1] if f.t <= t0 + COUNTER_S)
            if shot or box:
                p.counters += 1
                if shot:
                    p.counter_shots += 1
                    p.counter_ids.append(shot.event_id)
    p.regained = pct(regained, p.losses) if p.losses >= 8 else None

    p.mean_pos = _mean_positions(team, frames)
    p.shape_pos = _mean_positions(team, frames, centred=True)
    return p


def shape_of(xs: list[float], max_lines: int = 4, min_gap: float = 5.0) -> str:
    """Outfield x positions to a shape string: split at the largest gaps (at most 3 splits, each >= min_gap)."""
    xs = sorted(xs)
    gaps = sorted(((xs[i + 1] - xs[i], i) for i in range(len(xs) - 1)), reverse=True)
    cuts = sorted(i for g, i in gaps[:max_lines - 1] if g >= min_gap)
    sizes, start = [], 0
    for i in cuts:
        sizes.append(i + 1 - start)
        start = i + 1
    sizes.append(len(xs) - start)
    return "-".join(map(str, sizes))


def formation_of(roles: list[str]) -> str | None:
    """Formation from the line-up roles, e.g. 4-3-3. Wing-backs defend in a back five (with wide midfielders
    in front of them), otherwise they count as midfielders (3-4-2)."""
    rs = [r for r in roles if r and r != "GK"]
    if not rs:
        return None
    wide_mid = any(r in ("RM", "LM") for r in rs)
    d = sum(1 for r in rs if r in ("RB", "LB", "RCB", "CB", "LCB") or (r in ("RWB", "LWB") and wide_mid))
    f = sum(1 for r in rs if r in ("RW", "LW", "ST", "RS", "LS"))
    return f"{d}-{len(rs) - d - f}-{f}"


def _mean_positions(team: str, frames: list[FrameRel], centred: bool = False) -> dict[str, tuple[float, float]]:
    """Mean team-relative position per player; centred = relative to the outfield centroid of each frame."""
    acc: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for f in frames:
        field_ = [a for a in f.team[team] if a.role != "GK"]
        cx = mean(a.x for a in field_) if centred and field_ else 0.0
        cy = mean(a.y for a in field_) if centred and field_ else 0.0
        for a in f.team[team]:
            acc[a.id].append((a.x - cx, a.y - cy))
    need = max(1, len(frames) // 2)
    return {pid: (mean(x for x, _ in v), mean(y for _, y in v)) for pid, v in acc.items() if len(v) >= need}


def _role_in(frames: list[FrameRel], team: str, pid: str) -> str | None:
    for f in reversed(frames):
        for a in f.team[team]:
            if a.id == pid:
                return a.role
    return None


def heatmap(track: Track, team: str, frames: list[FrameRel]) -> Heatmap | None:
    """Share of the team's outfield presence per zone (%, absolute coordinates)."""
    if not frames:
        return None
    grid = [[0.0] * GRID_COLS for _ in range(GRID_ROWS)]
    n = 0
    for f in frames:
        for _, x, y in f.abs_[team]:
            c = min(GRID_COLS - 1, max(0, int(x / (L / GRID_COLS))))
            r = min(GRID_ROWS - 1, max(0, int(y / (W / GRID_ROWS))))
            grid[r][c] += 1
            n += 1
    if not n:
        return None
    return Heatmap(team=team_id(team), grid=[[round(100 * v / n, 1) for v in row] for row in grid],
                   dir=1 if track.attacks_right(team, frames[-1].period) else -1)


# ============================================================================ facts

@dataclass
class Draft:
    """A fact before it gets its id. `change` = it describes a deviation (sorted first)."""
    text: str
    metric: str
    value: float | str
    team: str
    concept: str
    unit: str | None = None
    src: list[int] = field(default_factory=list)
    change: bool = False


def _vs(value: float | None, prev: float | None, base: float | None, unit: str, prev_label: str,
        min_change: float) -> tuple[str, bool]:
    """' (previous 5 minutes: 41%, down 13 points; cup match: 52%)' and whether it changed enough."""
    parts, changed = [], False
    if value is None:
        return "", False
    points = " points" if unit == "%" else unit
    for label, ref in ((prev_label, prev), ("cup match", base)):
        if ref is None:
            continue
        diff = round(value - ref)
        part = f"{label}: {ref:g}{unit}"
        if abs(diff) >= min_change:
            changed = True
            part += f", {'up' if diff > 0 else 'down'} {abs(diff)}{points}"
        parts.append(part)
    return (f" ({'; '.join(parts)})" if parts else ""), changed


class Tactician:
    """Builds TacticalFactSheets for one match. Construct once per match (it turns the
    tracking team-relative once); every call only looks at data up to its `to_t`."""

    def __init__(self, info: MatchInfo, roster: dict[str, PlayerInfo], frames: list[SourceFrame],
                 baseline: list[Fact] | None = None) -> None:
        self.info, self.roster = info, roster
        self.track = Track(info, frames)
        self.baseline = baseline or []
        self._base = {(f.team, f.metric): f for f in self.baseline}

    # ------------------------------------------------------------------ helpers

    def name(self, team: str) -> str:
        return self.info.team_names.get(team, team)

    def who(self, pid: str | None) -> str:
        p = self.roster.get(pid or "")
        return f"{p.surname} ({p.n})" if p else (pid or "")

    def base(self, team: str, metric: str) -> float | str | None:
        f = self._base.get((team_id(team), metric))
        return f.value if f else None

    def label(self, from_t: float, to_t: float) -> str:
        fs = self.track.window(from_t, to_t)
        if not fs:
            return ""
        return f"{_clock_minute(fs[0].clock, up=False)}'–{_clock_minute(fs[-1].clock, up=True)}'"

    def prints(self, from_t: float, to_t: float, events: list[SourceEvent]) -> dict[str, Print]:
        frames = self.track.window(from_t, to_t)
        evs = [e for e in events if from_t <= e.t <= to_t]
        return {team: fingerprint(self.track, team, frames, evs) for team in (self.info.home, self.info.away)}

    # ------------------------------------------------------------------ detectors -> drafts

    def drafts(self, now: Print, prev: Print | None, prev_label: str) -> list[Draft]:
        team, name, out = now.team, self.name(now.team), []
        pv = (lambda attr: getattr(prev, attr) if prev else None)

        # B1 / B2: where the 6 stands in build-up
        if now.dm_between is not None:
            six = f"{name}'s 6, {self.who(now.dm_id)},"
            base = self.base(team, "dm_between_pct")
            cmp_, changed = _vs(now.dm_between, pv("dm_between"), base, "%", prev_label, 20)
            line = ""
            if now.last_line_in_poss:
                line = f"; {now.last_line_in_poss} in the last line in build-up"
                if now.last_line_out_poss:
                    line += f" against {now.last_line_out_poss} without the ball"
            if now.dm_between >= 30 or changed:
                out.append(Draft(f"{six} dropped between the centre-backs in {now.dm_between:g}% of {now.phases} build-up phases"
                                 f"{cmp_}{line}", "dm_between_pct", now.dm_between, team, "B1", "%", change=changed))
            cmp_, changed = _vs(now.dm_beside, pv("dm_beside"), self.base(team, "dm_beside_pct"), "%", prev_label, 20)
            if now.dm_beside is not None and (now.dm_beside >= 30 or changed):
                side = f", mostly on the {now.dm_beside_side}" if now.dm_beside_side else ""
                out.append(Draft(f"{six} dropped beside a centre-back in {now.dm_beside:g}% of {now.phases} build-up phases{side}{cmp_}",
                                 "dm_beside_pct", now.dm_beside, team, "B2", "%", change=changed))

        # B3: inverted full-backs
        for role, (pid, share) in now.fb_invert.items():
            prev_share = prev.fb_invert.get(role, (None, None))[1] if prev else None
            metric = f"fb_invert_{role.lower()}_pct"
            cmp_, changed = _vs(share, prev_share, self.base(team, metric), "%", prev_label, 20)
            if share >= 30 or changed:
                out.append(Draft(f"{name}'s {ROLE_NAMES[role]} {self.who(pid)} moved inside next to the 6 for {share:g}% "
                                 f"of the build-up time{cmp_}", metric, share, team, "B3", "%", change=changed))

        # B5: direct build-up
        if now.long_share is not None:
            cmp_, changed = _vs(now.long_share, pv("long_share"), self.base(team, "long_ball_pct"), "%", prev_label, 10)
            if now.long_share >= 20 or changed:
                out.append(Draft(f"{now.long_share:g}% of {name}'s {now.buildup_passes} passes from their own half went long{cmp_}", "long_ball_pct", now.long_share, team, "B5", "%", change=changed))

        # B6: build-up shape
        if now.shape:
            base = self.base(team, "buildup_shape")
            prev_shape = pv("shape")
            changed = bool((prev_shape and prev_shape != now.shape) or (base and base != now.shape))
            refs = "; ".join(x for x in ((f"{prev_label}: {prev_shape}" if prev_shape else ""),
                                         (f"cup match: {base}" if base else "")) if x)
            out.append(Draft(f"{name}'s build-up shape: {now.shape}" + (f" ({refs})" if refs else ""),
                             "buildup_shape", now.shape, team, "B6", change=changed))

        # P1: flank use
        if now.channels:
            ch = now.channels
            prev_ch = pv("channels") or {}
            base = {k: self.base(team, f"channel_{k}_pct") for k in ch}
            moved = [(k, ch[k] - prev_ch[k]) for k in ch if k in prev_ch]
            moved_base = [(k, ch[k] - base[k]) for k in ch if base[k] is not None]
            big = max(moved, key=lambda kv: abs(kv[1]), default=None)
            big_base = max(moved_base, key=lambda kv: abs(kv[1]), default=None)
            changed = bool((big and abs(big[1]) >= 12) or (big_base and abs(big_base[1]) >= 12))
            if max(ch["left"], ch["right"]) >= 40 or changed:
                text = f"{name}'s attacks: left {ch['left']:g}%, centre {ch['centre']:g}%, right {ch['right']:g}%"
                if big and abs(big[1]) >= 12:
                    k = big[0]
                    text += f"; {k} {prev_ch[k]:g}% → {ch[k]:g}% compared with the {prev_label}"
                if big_base and abs(big_base[1]) >= 12:
                    k = big_base[0]
                    text += f"; cup match: {k} {base[k]:g}%"
                top = max(ch, key=ch.get)
                out.append(Draft(text, f"channel_{top}_pct", ch[top], team, "P1", "%", change=changed))

        # P2: switches of play
        prev_sw = pv("switches")
        if now.switches >= 3 or (prev_sw is not None and abs(now.switches - prev_sw) >= 3):
            extra = f" ({prev_label}: {prev_sw})" if prev_sw is not None else ""
            out.append(Draft(f"{name} completed {now.switches} switches of play (over 30 m across){extra}",
                             "switches", now.switches, team, "P2", src=now.switch_ids[:10],
                             change=prev_sw is not None and abs(now.switches - prev_sw) >= 3))

        # D1: block height
        if now.line_m is not None:
            block = "high" if now.line_m >= 33 else "low" if now.line_m < 24 else "mid"
            cmp_, changed = _vs(now.line_m, pv("line_m"), self.base(team, "line_height_m"), " m", prev_label, 4)
            if block != "mid" or changed:
                out.append(Draft(f"{name} defended in a {block} block: last line {now.line_m:g} m from their own goal, "
                                 f"first line {now.first_line_m:g} m{cmp_}", "line_height_m", now.line_m, team, "D1", "m",
                                 change=changed))

        # D2: compactness
        if now.depth_m is not None:
            cmp_, changed = _vs(now.depth_m, pv("depth_m"), self.base(team, "compactness_m"), " m", prev_label, 4)
            if now.depth_m >= 35 or now.depth_m <= 26 or changed:
                verdict = "stretched" if now.depth_m >= 35 else "compact" if now.depth_m <= 26 else "medium"
                out.append(Draft(f"{name}'s block without the ball was {verdict}: {now.depth_m:g} m deep and "
                                 f"{now.width_m:g} m wide{cmp_}", "compactness_m", now.depth_m, team, "D2", "m",
                                 change=changed))

        # D3: pressing
        if now.ppda is not None:
            cmp_, changed = _vs(now.ppda, pv("ppda"), self.base(team, "ppda"), "", prev_label, 4)
            if now.ppda <= 8 or now.ppda >= 15 or changed or now.high_recoveries >= 2:
                level = "intense" if now.ppda <= 8 else "passive" if now.ppda >= 15 else "moderate"
                rec = (f", {now.high_recoveries} ball recover{'y' if now.high_recoveries == 1 else 'ies'} in the attacking third"
                       if now.high_recoveries else "")
                out.append(Draft(f"{name}'s press was {level}: PPDA {now.ppda:g}{rec}{cmp_}", "ppda", now.ppda, team,
                                 "D3", src=now.high_recovery_ids[:10], change=changed))

        # T1: counter-press
        if now.regained is not None:
            cmp_, changed = _vs(now.regained, pv("regained"), self.base(team, "counterpress_pct"), "%", prev_label, 25)
            if now.regained >= 35 or changed:
                out.append(Draft(f"{name} won the ball back within 5 seconds after {now.regained:g}% of {now.losses} "
                                 f"losses{cmp_}", "counterpress_pct", now.regained, team, "T1", "%", change=changed))

        # T3: counter-attacks
        if now.counters >= 3 or now.counter_shots >= 1:
            shots = f", {now.counter_shots} of them ending in a shot" if now.counter_shots else ""
            out.append(Draft(f"{name} reached the box or shot within 10 seconds of winning the ball {now.counters} "
                             f"times{shots}", "counters", now.counters, team, "T3", src=now.counter_ids))
        return out

    def formation_moves(self, now: Print, prev: Print) -> Draft | None:
        """G1: players whose mean position moved more than MOVED_M against the previous window."""
        moved = []
        for pid, (x, y) in now.shape_pos.items():
            if pid in prev.shape_pos and not (self.roster.get(pid) and self.roster[pid].gk):
                px, py = prev.shape_pos[pid]
                d = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
                if d > MOVED_M:
                    moved.append((d, pid, x - px))
        if len(moved) < 2:
            return None
        moved.sort(reverse=True)
        parts = [f"{self.who(pid)} {round(d)} m {'forward' if dx > 0 else 'back' if dx < 0 else 'across'}"
                 for d, pid, dx in moved[:3]]
        return Draft(f"{len(moved)} {self.name(now.team)} players' positions within the team shape moved more than 10 m: "
                     + ", ".join(parts),
                     "players_moved", len(moved), now.team, "G1", change=True)

    def shape_changes(self, events: list[SourceEvent], from_t: float, to_t: float) -> list[Draft]:
        """G1 from the events: a declared change of formation in the window."""
        out = []
        for e in events:
            if not (from_t <= e.t <= to_t) or e.type not in ("substitution", "tactical_change"):
                continue
            if any(d.metric == "formation" and d.team == e.team for d in out):
                continue
            old, new = self.formation_at(e.team, e.t - 1), self.formation_at(e.team, min(to_t, e.t + 30))
            if old and new and old != new:
                out.append(Draft(f"{self.name(e.team)} changed from a {old} to a {new} at {e.minute}'", "formation", new,
                                 e.team, "G1", src=[e.event_id], change=True))
        return out

    def formation_at(self, team: str, t: float) -> str | None:
        fs = self.track.window(max(0.0, t - 5), t)
        return formation_of([a.role for a in fs[-1].team[team]]) if fs else None

    def substitution(self, subs: list[SourceEvent], events: list[SourceEvent], to_t: float) -> list[Draft]:
        """G2: 10 minutes before the substitution(s) of one team at one moment against the time since."""
        sub = subs[0]
        team = sub.team
        before = self.prints(max(0.0, sub.t - SUB_BEFORE_S), sub.t - 1, events)[team]
        after = self.prints(sub.t, to_t, events)[team]
        ins = " and ".join(self.who(s.details.get("player_in_id")) for s in subs)
        name, since = self.name(team), f"Since {ins} came on at {sub.minute}'"
        src = [s.event_id for s in subs]
        out = []
        if before.possession is not None and after.possession is not None:
            d = round(after.possession - before.possession)
            trend = (f"{'rose' if d > 0 else 'fell'} from {before.possession:g}% to {after.possession:g}%, {abs(d)} points"
                     if d else f"stayed at {after.possession:g}%")
            out.append(Draft(f"{since}, {name}'s possession {trend}", "sub_possession", after.possession, team, "G2", "%",
                             src=src, change=abs(d) >= 8))
        if before.channels and after.channels:
            k, d = max(((k, after.channels[k] - before.channels[k]) for k in after.channels), key=lambda kv: abs(kv[1]))
            if abs(d) >= 8:
                where = "through the centre" if k == "centre" else f"down the {k}"
                out.append(Draft(f"{since}, the share of {name}'s attacks {where} {'rose' if d > 0 else 'fell'} from "
                                 f"{before.channels[k]:g}% to {after.channels[k]:g}%", f"sub_channel_{k}_pct",
                                 after.channels[k], team, "G2", "%", src=src, change=True))
        if before.line_m is not None and after.line_m is not None and abs(after.line_m - before.line_m) >= 3:
            d = round(after.line_m - before.line_m)
            out.append(Draft(f"{since}, {name}'s last line without the ball moved {'up' if d > 0 else 'back'} from "
                             f"{before.line_m:g} m to {after.line_m:g} m", "sub_line_height_m", after.line_m, team, "G2",
                             "m", src=src, change=True))
        for s in subs:
            pin, pout = s.details.get("player_in_id"), s.player_id
            # Zones within the team shape (centroid-relative), so a team that is pinned back is not a zone change.
            a, b = after.shape_pos.get(pin), before.shape_pos.get(pout)
            ya, yb = after.mean_pos.get(pin), before.mean_pos.get(pout)
            if not (a and b and ya and yb):
                continue
            d = round(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)
            same = channel(ya[1]) == channel(yb[1]) and d < 12
            zone = lambda p: "in the centre" if channel(p[1]) == "centre" else f"on the {channel(p[1])}"
            depth = "" if abs(a[0] - b[0]) < 6 else f", {round(abs(a[0] - b[0]))} m {'higher' if a[0] > b[0] else 'deeper'} in the team shape"
            out.append(Draft(f"{self.who(pin)} has played {zone(ya)}{depth}; {self.who(pout)}, the player replaced, played "
                             f"{zone(yb)} ({'like for like' if same else 'a different role'})",
                             "sub_zone_shift_m", d, team, "G2", "m", src=[s.event_id], change=not same))
        return out

    def game_state(self, events: list[SourceEvent], to_t: float) -> list[Draft]:
        """G3: block height and possession split by game state, over the match so far."""
        goals = [e for e in events if e.type == "goal" and e.t <= to_t]
        reds = [e for e in events if e.type == "red_card" and e.t <= to_t]
        frames = self.track.window(0, to_t)
        out = []
        for team in (self.info.home, self.info.away):
            opp = self.info.away if team == self.info.home else self.info.home
            by_state: dict[str, list[FrameRel]] = defaultdict(list)
            for f in frames:
                if not f.live:
                    continue
                g = [e for e in goals if e.t <= f.t]
                last = g[-1] if g else None
                for_, against = (last.score_home, last.score_away) if last else (0, 0)
                if team != self.info.home:
                    for_, against = against, for_
                state = "leading" if for_ > against else "trailing" if for_ < against else "level"
                men = [e.team for e in reds if e.t <= f.t]
                if team in men:
                    state += " with 10 men"
                elif opp in men:
                    state += " against 10 men"
                by_state[state].append(f)
            lines = {}
            for state, fs in by_state.items():
                out_f = [f for f in fs if f.poss == opp]
                if len(out_f) >= 3 * MIN_FRAMES:
                    lines[state] = round(mean(mean(sorted(a.x for a in f.team[team] if a.role != "GK")[:4]) for f in out_f))
            if len(lines) >= 2 and max(lines.values()) - min(lines.values()) >= 3:
                parts = ", ".join(f"{v} m when {k}" for k, v in lines.items())
                out.append(Draft(f"{self.name(team)}'s last line without the ball so far: {parts}", "line_by_state",
                                 max(lines.values()) - min(lines.values()), team, "G3", "m"))
        return out

    # ------------------------------------------------------------------ the sheet

    def sheet(self, trigger: TacticalTrigger, from_t: float, to_t: float, events: list[SourceEvent],
              snapshot: MatchSnapshot | None = None, prev: tuple[float, float] | None = None,
              subs: list[SourceEvent] | None = None, max_facts: int = 12) -> TacticalFactSheet | None:
        """The tactical fact sheet of [from_t, to_t]; None when nothing meaningful was measured.

        `events` may contain the whole match: only events up to `to_t` are used."""
        events = [e for e in events if e.t <= to_t]
        label = self.label(from_t, to_t)
        now = self.prints(from_t, to_t, events)
        before = self.prints(*prev, events) if prev else {}
        prev_label = f"previous {round((prev[1] - prev[0] + 1) / 60)} minutes" if prev else ""
        drafts: list[Draft] = []
        if subs:
            drafts += self.substitution(subs, events, to_t)
        drafts += self.shape_changes(events, from_t, to_t)
        for team in (self.info.home, self.info.away):
            drafts += self.drafts(now[team], before.get(team), prev_label)
            if team in before and not any(d.concept == "G1" and d.team == team for d in drafts):
                moved = self.formation_moves(now[team], before[team])
                if moved:
                    drafts.append(moved)
        if trigger == "half_time" or (trigger == "interval" and round(to_t / 60) % 15 == 0):
            drafts += self.game_state(events, to_t)     # over the match so far: every 15 minutes is enough
        if trigger in ("interval", "substitution"):
            # A short window only repeats the structure for the core concepts; the rest must have changed.
            drafts = [d for d in drafts if d.change or d.concept in CORE_STATIC]
        if not drafts:
            return None
        # Substitution and formation facts first, then what changed, then the structure.
        rank = {"G2": 0, "G1": 1}
        drafts.sort(key=lambda d: (rank.get(d.concept, 2), not d.change))
        drafts = drafts[:max_facts]
        facts = [Fact(fact_id=f"T{i}", text=d.text, metric=d.metric, value=d.value, unit=d.unit, window=label,
                      source_event_ids=d.src, team=team_id(d.team), concept=d.concept)
                 for i, d in enumerate(drafts, start=1)]
        cited = {(f.team, f.metric) for f in facts}
        baseline = [b for b in self.baseline if (b.team, b.metric) in cited]
        home, away = team_id(self.info.home), team_id(self.info.away)
        score = f" {self.name(self.info.home)} {snapshot.score[0]}-{snapshot.score[1]} {self.name(self.info.away)}" if snapshot else ""
        frames = self.track.window(from_t, to_t)
        return TacticalFactSheet(
            window=TacticalWindow(from_t=from_t, to_t=to_t, label=label), trigger=trigger,
            minute=minute_from_clock(frames[-1].clock) if frames else "",
            headline=f"Tactics {label}:{score}" if score else f"Tactics {label}",
            home=home, away=away, team_names={home: self.name(self.info.home), away: self.name(self.info.away)},
            match_state=snapshot, facts=facts, baseline=baseline,
            concepts_fired=list(dict.fromkeys(f.concept for f in facts)),
        )

    # ------------------------------------------------------------------ for the frontend and the scouting report

    def heatmap(self, team: str, from_t: float, to_t: float) -> Heatmap | None:
        return heatmap(self.track, team, self.track.window(from_t, to_t))

    def build_up_positions(self, team: str, from_t: float, to_t: float) -> list[Player]:
        """Mean absolute positions in the team's build-up frames (shows where the 6 stands)."""
        frames = [f for f in self.track.window(from_t, to_t) if f.live and f.poss == team and f.ball[team][0] < HALF]
        if len(frames) < MIN_FRAMES:
            return []
        acc: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for f in frames:
            for a in f.team[team]:
                acc[a.id].append(self.track.rel(team, f.period, a.x, a.y))  # rel twice = absolute again
        out = []
        for pid, v in acc.items():
            if len(v) < len(frames) // 2:
                continue
            info = self.roster.get(pid)
            out.append(Player(id=pid, team=team_id(team), n=info.n if info else 0,
                              x=round(mean(x for x, _ in v), 1), y=round(mean(y for _, y in v), 1),
                              gk=info.gk if info else None, name=info.name if info else None))
        return out

    def baseline_facts(self, events: list[SourceEvent], from_t: float, to_t: float) -> list[Fact]:
        """The whole-match fingerprint as baseline facts (ids C1, C2, ...): every metric, no thresholds."""
        prints = self.prints(from_t, to_t, events)
        out: list[tuple[str, str, float | str, str, str | None]] = []
        for team, p in prints.items():
            n = self.name(team)
            if p.dm_between is not None:
                out.append((f"Cup match: {n}'s 6, {self.who(p.dm_id)}, dropped between the centre-backs in {p.dm_between:g}% of {p.phases} build-up phases",
                            "dm_between_pct", p.dm_between, team, "B1"))
                out.append((f"Cup match: {n}'s 6 dropped beside a centre-back in {p.dm_beside:g}% of {p.phases} build-up phases",
                            "dm_beside_pct", p.dm_beside, team, "B2"))
            for role, (pid, share) in p.fb_invert.items():
                out.append((f"Cup match: {n}'s {ROLE_NAMES[role]} {self.who(pid)} moved inside next to the 6 for {share:g}% of the build-up time",
                            f"fb_invert_{role.lower()}_pct", share, team, "B3"))
            if p.long_share is not None:
                out.append((f"Cup match: {p.long_share:g}% of {n}'s passes from their own half went long", "long_ball_pct", p.long_share, team, "B5"))
            if p.shape:
                out.append((f"Cup match: {n}'s build-up shape {p.shape}", "buildup_shape", p.shape, team, "B6"))
            if p.channels:
                for k, v in p.channels.items():
                    out.append((f"Cup match: {v:g}% of {n}'s attacks went down the {k}", f"channel_{k}_pct", v, team, "P1"))
            if p.line_m is not None:
                out.append((f"Cup match: {n}'s last line without the ball {p.line_m:g} m from their own goal", "line_height_m", p.line_m, team, "D1"))
                out.append((f"Cup match: {n}'s block {p.depth_m:g} m deep without the ball", "compactness_m", p.depth_m, team, "D2"))
            if p.ppda is not None:
                out.append((f"Cup match: {n}'s PPDA {p.ppda:g}", "ppda", p.ppda, team, "D3"))
            if p.regained is not None:
                out.append((f"Cup match: {n} won the ball back within 5 seconds after {p.regained:g}% of losses", "counterpress_pct", p.regained, team, "T1"))
        return [Fact(fact_id=f"C{i}", text=text, metric=metric, value=value, window="cup match",
                     team=team_id(team), concept=concept)
                for i, (text, metric, value, team, concept) in enumerate(out, start=1)]
