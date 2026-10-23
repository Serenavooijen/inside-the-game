# Premier-League-Hackathon

A fully synthetic, scripted football match for the *Inside the Game* hackathon, with a full analysis along the 12 components of football analysis.

| File | What |
|---|---|
| `docs/DRAAIBOEK.md` | Match script: pre-match context (form, absences, schedule, coaches, set-piece profiles, match-ups), teams and players, phases, minute-by-minute moments, card and substitution effects with measured impact |
| `docs/MATCH_ANALYSIS.md` | Analysis: attacking, defending, transitions, tactics, players, physical/mental, set pieces, advanced stats (xG, xGA, xGOT, PPDA, field tilt, progressive passes, deep completions, big chances, xT, set-piece xG), match-ups, context, coaching |
| `script/match_script.json` | The script as data (source of truth for the match) |
| `script/pre_match_context.json` | Pre-match context as data |
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
