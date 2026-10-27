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

## Step plan

Each phase builds on the previous one and ends with something that runs. Phases 1 and 2 need no licence and no paid data.

### Phase 1: a real match, replayed

Goal: a real match plays in the frontend the way the synthetic one does now.

1. **Pick the data.** A Metrica Sports sample match: full tracking at 25 Hz plus events, so every part of the backend is tested.
2. **Write `MetricaSource`** next to `GeneratorSource`: coordinates (Metrica uses 0-1) to 105 × 68, time to `t`, event types to `SourceEventType`, ids, squad and team names (see *What an adapter has to do*).
3. **Make the backend frame-rate independent** (point 3 above): possession weighted by frame duration, the sprint rule in seconds instead of frames. Keep sending one `tick` per match second, so the frontend does not change.
4. **Fill the gaps in the data.** Metrica has no xG: add a simple xG model from shot distance and angle, so the shot overlay and the goal facts keep working.
5. **Tests**, as for the synthetic match: every event fits the contracts, the final score and shot count match the published result.
6. **A second adapter for StatsBomb Open Data** (events only). This tests the path without tracking (point 4): score, xG, cards and goal facts without moving players.

Done when: the Metrica match runs in the frontend with moving players, the right score, overlays and checked insights on every goal.

### Phase 2: live-capable, with "fake live"

Goal: the backend handles a feed that arrives in real time and never ends early, before any paid feed is involved.

1. **`LiveReplaySource`**: wraps any replay source and releases its items at the real clock, as a live feed would.
2. **Live mode in the simulator** (point 1 above): read the source as a running stream instead of up front, follow the feed's time, no speed control, seek only back to what has been received (`live_head_t`), no fixed duration.
3. **Broadcast delay instead of slowing down** (point 2 above): hold the picture back by a configurable delay (for example `ITG_LIVE_DELAY_S`, about 6-10 s) so that the explanation of a goal is ready when the goal is shown.
4. **Frontend live state**: a timeline without a fixed end and a "LIVE" indicator.
5. **Run Recorder**: record every live run as JSONL, so it can be replayed afterwards without model calls.
6. **A full 90 minutes in real time**: a long run with reconnects, to find memory growth, dropped connections and drift between the clock and the feed.

Done when: the Metrica match runs as fake live for 90 minutes, insights arrive together with the goals after the delay, and a reconnecting browser shows the right picture.

### Phase 3: a licensed feed

Goal: one real match, live, at a pilot.

1. **Choose a provider and agree terms**: licence, broadcast and display rights, a test or sandbox feed, and the provider's own delay.
2. **Write the provider adapter**: connect (push, websocket or polling), reconnect after a drop, and drop duplicate events.
3. **Handle corrections.** Providers change events afterwards (a goal disallowed by VAR, a different scorer, an updated xG). This needs a correction message in the contracts and a way to undo a published event, overlay or insight.
4. **Set the broadcast delay** from the measured delay of the feed plus the time the agents need.
5. **Cost and safety**: a budget for model calls per match, the kill switch for all model calls, rate limits on the public endpoints.
6. **A pilot**: one real match end to end, recorded, then reviewed against the TV broadcast.

Done when: a real match runs live with checked insights, and the recording replays without model calls.

### Phase 4: more matches and real history

1. **State per match** instead of one global simulator, so one backend can serve several matches.
2. **EventBus to Azure Event Hubs or Service Bus** (already the growth path in the architecture), with the agents as separate workers that scale on their own.
3. **The Scout's baseline from real history**: the previous real meetings between the two teams instead of the synthetic cup match.
