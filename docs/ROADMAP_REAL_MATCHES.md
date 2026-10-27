# Roadmap: from a synthetic match to real matches

The demo plays a synthetic match, because no match data was provided. The backend is built so that a real match is a new data source, not a rebuild. This page says what is ready, what a real source has to deliver and what still has to change.

## What is ready

- **One way in.** Match data enters the backend only through `MatchSource` (`backend/app/sources.py`). The synthetic match is one implementation (`GeneratorSource` in `backend/app/fixture.py`). A real feed is another class next to it.
- **Contracts that allow live data.** `backend/app/contracts.py` has `mode: "live"`, time as seconds with fractions, extra time and penalties (`period` 1-5), an `"other"` event type for anything unknown, and room for provider ids in `details`.
- **Everything downstream works incrementally and only looks at the past.** The Stats Engine, the Overlay Composer and the Statistician (which builds the facts for the agents) update per event and per frame, exactly as they would during a live match.

```
real feed ──► adapter (MatchSource) ──► Stats Engine / Overlays / Statistician ──► agents ──► frontend
              new                       unchanged
```

## Data sources

| Source | What it gives | Live |
|---|---|---|
| Licensed event feeds (for example Opta/Stats Perform, StatsBomb, Wyscout) | Events with xG, assists, substitutions | Yes, paid and licensed |
| Tracking data (a league's official tracking, or tracking from broadcast video) | Positions of all players and the ball | Yes, expensive and rarely available to third parties |
| StatsBomb Open Data | Real historical matches: events and line-ups, some with 360 freeze frames | No |
| Metrica Sports sample data | A few anonymised matches with full tracking and events | No |
| Auto-eventing from video | Events made by our own model (growth path in the architecture) | Yes, a project of its own |

The two open sources are the cheapest way to test with real data, without a licence.

## What an adapter has to do

- **Coordinates** to absolute metres, 105 × 68 (StatsBomb uses 120 × 80, Opta 0-100).
- **Time** from period and timestamp to one continuous `t`.
- **Event types** to `SourceEventType`; anything else becomes `"other"` with the original in `details["provider_type"]`.
- **Ids**: an ascending `event_id`, with the provider's id in `details["provider_event_id"]`.
- **The fields the backend reads** in `details`, where the provider has them: `xg`, `xgot`, `body_part`, `distance_m`, `big_chance`, `assist_id`, `player_in_id`, `second_yellow`, `pass_type`, `length_m`. A missing field drops the fact that needs it; nothing breaks.
- **Squad and teams**: `roster` (shirt number, name, goalkeeper) and `team_names`.

## What still has to change in the backend

1. **Reading the source.** `Simulator.load()` reads the whole source before it starts (`backend/app/simulator.py`, `items = [item async for item in source.items(0)]`) and takes the duration from the last item. A live feed never ends. In live mode the simulator has to process items as they arrive, without a speed setting, with seek only back in time (up to `live_head_t`).
2. **Key moments.** On a goal the replay slows to 1× until the explanation is ready. Reality cannot be slowed down. The live equivalent is what broadcasters already do: run the whole picture a few seconds behind (about 6-10 s), so the explanation arrives together with the goal.
3. **Tracking at 25 Hz.** Two places assume one frame per second:
   - the Stats Engine counts possession as one second per frame (`backend/app/stats.py`); it has to weigh each frame by its duration;
   - the sprint rule looks back a number of frames for the start of a run (`backend/app/overlays.py`, `SPRINT_TRAIL_S`); it has to look back in seconds.
4. **Without tracking** (events only) there are no moving players, sprints, defensive line or tactical facts. Score, xG, cards and most goal facts still work.
5. **Synthetic-only details.**
   - The tag overlay also uses `scripted` chances.
   - Card facts use the referee's `reason`, which feeds rarely provide as text.
   - The Scout compares with the earlier cup match between the same teams (`output/cup/`); with real data that becomes the previous real meeting.

## Order of work

1. **A replay adapter for StatsBomb Open Data or Metrica.** It proves the seam with real data, without a licence or a network. Metrica includes tracking, which tests point 3.
2. **A "fake live" source.** The same real match, released in real time. It makes the simulator live-capable (points 1 and 2) before any paid feed is involved.
3. **A licensed feed.** Next to the adapter, this needs agreements on the licence, broadcast rights and the delay of the feed.
