# Premier-League-Hackathon

A fully synthetic, scripted football match for the *Inside the Game* hackathon, with a full analysis along the 12 components of football analysis.

| File | What |
|---|---|
| `docs/DRAAIBOEK.md` | Match script: pre-match context (form, absences, schedule, coaches, set-piece profiles, match-ups), teams and players, phases, minute-by-minute moments, card and substitution effects with measured impact |
| `docs/MATCH_ANALYSIS.md` | Analysis: attacking, defending, transitions, tactics, players, physical/mental, set pieces, advanced stats (xG, xGA, xGOT, PPDA, field tilt, progressive passes, deep completions, big chances, xT, set-piece xG), match-ups, context, coaching |
| `script/match_script.json` | The script as data (source of truth for the match) |
| `script/pre_match_context.json` | Pre-match context as data |
| `script/cup/match_script.json` | The earlier cup match between the same teams (seed 4417), the Scout's baseline → `output/cup/`, `fixtures/scouting/` |
| `generator/generate_match.py` | 1 Hz match simulator that follows the script |
| `generator/analyze_match.py` | Computes all analysis metrics → `output/analysis.json` + figures |
| `generator/render_analysis.py` / `render_draaiboek.py` | Build the two Markdown documents in `docs/` |
| `output/` | events, tracking (1 frame/sec), per-minute stats, player stats, analysis, morale timeline, tactics, figures |

```bash
pip install numpy matplotlib
python generator/generate_match.py
python generator/analyze_match.py
python generator/render_analysis.py
python generator/render_draaiboek.py
```

## Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload   # http://localhost:8000/health
uv run pytest
```

The generator dependencies (numpy, matplotlib) are in the backend's dev group, so from `backend/` you can also run `uv run python ../generator/generate_match.py`.

The backend replays the reference match from `output/` and streams it over SSE in the shapes of `frontend/lib/contracts.ts`. To run the frontend against it instead of its mock, set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`. The agents use `MODEL_PROVIDER` (default `offline`, no model calls); see `docs/overdracht-agents.md` for Foundry.

| Module | Role |
|---|---|
| `app/fixture.py` | `MatchSource` for the generator output |
| `app/simulator.py` | play, pause, speed, seek, key moments; one `tick` per match second |
| `app/stats.py` | Stats Engine: score, xG, possession, updated per event and frame |
| `app/wire.py` | source data → frontend contract (events, frames, markers) |
| `app/bus.py` | EventBus: a bounded queue per SSE connection; drops the oldest when full |
| `app/overlays.py` | Overlay Composer (fast lane): shot, pass, sprint and tag overlays, per event and frame |
| `app/moments.py` | Statistician: recognises moments (goals, cards, half and full time) and builds their FactSheet |
| `app/smart_lane.py` | Runs the agent workflow per moment: at most 2 at once, 8 s safety net, cancelled on seek |
| `app/tactics.py` | Tactician: tactical facts per window, one detector per concept in `agents/knowledge/tactics_playbook.md` |
| `app/scout_lane.py` | Runs the Scout every 5 minutes, at half time and after substitutions (`TACTICS_ENABLED=1`) |
| `app/commentary_lane.py` | One checked line of commentary per minute, SSE `commentary` (`TACTICS_ENABLED=1`) |

### Tactical analysis (`TACTICS_ENABLED=1`)

With `TACTICS_ENABLED=1` the backend adds the **Scout**, a third agent: an opposition analyst for the staff.

- **When:** every 5 minutes of match time, at half time, and 3 minutes after a team's substitution(s).
- **How:**
  1. The code measures tactical facts in `app/tactics.py`, one detector per concept in `app/agents/knowledge/tactics_playbook.md`, compared with the earlier cup match.
  2. The Scout writes 2–3 observations, each with a consequence and advice for the coach.
  3. The checker rejects numbers, names, score claims and directions that the facts do not back.
- **Output:** the result is sent as an `insight` of type `"tactics"`. The scouting report on the cup match (`fixtures/scouting/kba-ngr-cup.json`) is sent in `state.scouting`.
- **Commentary:** every match minute the Narrator writes one checked line (≤ 25 words), sent as the new SSE message **`commentary`** `{ t, minute, text, sourceInsightId, generation }`.
- **The match itself:** the live match is unchanged (seed 8002, 2-2, xG 2.48–1.52). The cup match (`script/cup/`) is only the baseline.

Container App settings for it (all of them in `docs/overdracht-agents.md`, section 5):

| Setting | Value |
|---|---|
| `TACTICS_ENABLED` | `1` |
| `FOUNDRY_SCOUT_AGENT` / `FOUNDRY_SCOUT_AGENT_VERSION` | `itg-scout` / `3` (publish with `tools/create_foundry_agents.py --only scout`) |
| `SCOUT_DEADLINE_S`, `COMMENTARY_DEADLINE_S` | optional, default 15 and 5 |

### Docker and Azure Container Apps

`backend/Dockerfile` builds the backend image from the repo root. The reference match is generated from its seed during the build, so the image does not depend on `output/` in git.

```bash
docker build -f backend/Dockerfile -t itg-backend .                       # with Docker
az acr build -r <registry> -t itg-backend:<tag> -f backend/Dockerfile .   # in Azure, no local Docker needed
```

Container App settings:

| Setting | Value |
|---|---|
| Replicas | min 1, max 1 (match state lives in memory) |
| Ingress | external, target port 8000 |
| Health probe | `GET /health` |
| `ITG_CORS_ORIGINS` | the frontend URL(s), comma-separated |
| `MODEL_PROVIDER` and Foundry variables | see `docs/overdracht-agents.md`, section 5 |
| Identity | system-assigned managed identity with *Cognitive Services User* on the Foundry resource |
