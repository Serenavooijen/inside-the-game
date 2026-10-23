"""Translates source data into the frontend contract (layer 1 of contracts.py).

The same rules as frontend/scripts/import_generator.py, so the real backend and the
frontend's mock show the same events, texts and positions.
"""
from app.contracts import Frame, Marker, MatchEvent, Player, Point, SourceEvent, SourceFrame
from app.sources import PlayerInfo


def team_id(source_team: str) -> str:
    """Source team code to frontend team id: "KBA" -> "kba"."""
    return source_team.lower()


def minute_from_clock(clock: str) -> str:
    """Football minute label from the match clock: "23:14" -> "24", "45+1:30" -> "45+2"."""
    mm = clock.split(":")[0]
    if "+" in mm:
        base, extra = mm.split("+")
        return f"{base}+{int(extra) + 1}"
    return str(int(mm) + 1)


def to_frame(f: SourceFrame, roster: dict[str, PlayerInfo]) -> Frame:
    players = []
    for p in f.players:
        info = roster.get(p.id)
        players.append(Player(
            id=p.id, team=team_id(p.team), n=info.n if info else 0,
            x=round(p.x, 1), y=round(p.y, 1),
            gk=info.gk if info else None, name=info.name if info else None,
        ))
    return Frame(t=f.t, players=players, ball=Point(x=round(f.ball.x, 1), y=round(f.ball.y, 1)))


def to_match_event(e: SourceEvent, roster: dict[str, PlayerInfo]) -> MatchEvent | None:
    """Goals, cards and substitutions for the scorebar and timeline; None for everything else."""
    def surname(pid: str | None) -> str:
        return roster[pid].surname if pid in roster else (pid or "")

    def named(pid: str) -> str:
        return f"{surname(pid)} ({roster[pid].n})" if pid in roster else surname(pid)

    if e.team is None:
        return None
    base = dict(id=f"e-{e.event_id}", t=e.t, minute=e.minute, team=team_id(e.team))
    if e.type == "goal":
        assist = e.details.get("assist_id")
        detail = named(e.player_id) + (f" · assist {named(assist)}" if assist else "")
        return MatchEvent(**base, kind="goal", player_id=e.player_id, text=f"{surname(e.player_id)} {e.minute}'",
                          detail=detail, key=True)
    if e.type == "yellow_card" and not e.details.get("second_yellow"):
        return MatchEvent(**base, kind="yellow", player_id=e.player_id, text=f"{surname(e.player_id)} {e.minute}'")
    if e.type == "red_card":
        reason = str(e.details.get("reason", "sent off")).lower()
        return MatchEvent(**base, kind="red", player_id=e.player_id, text=f"{surname(e.player_id)} {e.minute}'",
                          detail=f"{named(e.player_id)} · {reason}", key=True)
    if e.type == "substitution":
        pid = e.details.get("player_in_id")
        return MatchEvent(**base, kind="sub", player_id=pid, text=f"{surname(pid)} {e.minute}'")
    return None


def markers(events: list[MatchEvent]) -> list[Marker]:
    """Timeline markers for replay mode (frontend/lib/markers.ts; corrected claims follow with insights)."""
    kinds = {"goal": ("goal", "Goal"), "yellow": ("card", "Yellow card"), "red": ("red", "Red card")}
    return [
        Marker(t=e.t, minute=e.minute, kind=kinds[e.kind][0], team=e.team, title=f"{kinds[e.kind][1]} {e.text}")
        for e in events if e.kind in kinds
    ]
