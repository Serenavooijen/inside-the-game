# Premier-League-Hackathon

A fully synthetic, scripted football match for the *Inside the Game* hackathon, with a full analysis along the 12 components of football analysis.

| File | What |
|---|---|
| `docs/DRAAIBOEK.md` | Match script: pre-match context (form, absences, schedule, coaches, set-piece profiles, match-ups), teams and players, phases, minute-by-minute moments, card and substitution effects with measured impact |
| `docs/MATCH_ANALYSIS.md` | Analysis: attacking, defending, transitions, tactics, players, physical/mental, set pieces, advanced stats (xG, xGA, xGOT, PPDA, field tilt, progressive passes, deep completions, big chances, xT, set-piece xG), match-ups, context, coaching |
| `docs/ROADMAP_REAL_MATCHES.md` | From the synthetic match to real matches: what is ready, what a real data source must deliver, what still has to change |
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
| `app/translation_lane.py` | Translates every finished, checked card afterwards (`ITG_LANGUAGES`); the live agents go first |

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

### Languages (`ITG_LANGUAGES`)

Insights for fans in English, Dutch, Spanish and French. The rule stays: the AI writes, the code checks. The fact-check is built on English (number words, comparatives, the game state), so the agents keep writing and checking in English. Translation is a separate step:

1. **English first, unchanged.** The workflow makes a checked English card (status `checked` or `corrected`) and streams it as before.
2. **Translate.** When the card is done, the **Translator** (`itg-translator`, gpt-4.1-mini, hosted in Foundry like the other agents) translates only that checked text: literally and naturally, nothing added or left out, numbers as digits, names of players and clubs unchanged. A card goes in chunks of 3 texts, in parallel. A translation waits while a live moment is being analysed (at most 10 s), so it never takes model capacity from a goal.
3. **Check again, in code** (`check_translation` in `app/agents/checker.py`). Every translated text is compared with its English source:
   - the same numbers: 0,41 = 0.41; English number words count in the source, the target language's in the translation (`drie`, `tres`, `trois`);
   - the same names: every player and club of the source is in it (a Dutch genitive `Brouwers` is fine), and no capitalised word comes in that is not in the source;
   - a sane length: at most about twice the source.
4. **Send.** The same insight (same id) goes out once more with `translations: { nl: {...}, es: {...}, fr: {...} }`, each with the translated fields and a status `checked` or `rejected` plus a reason. The same applies to the commentary line.

A translation that fails the check, or comes later than `TRANSLATE_DEADLINE_S` (6 s, separate from the agents' deadlines), is `rejected`: the app shows the English text with a small **EN** label. An unchecked translation is never shown.

- **What is translated:** the text of moment cards; observation, consequence and coach advice of tactics cards; the Scout's substitution cards (watch points and impact); the commentary line; the scouting report (translated at load, `SCOUTING_TRANSLATE_DEADLINE_S` 30 s). **Evidence** lines are the facts and stay English; the UI marks them as *Source data · EN*.
- **Cache:** per text and per language, in memory, so the same text is never translated twice, also not after a seek. Translations of an old generation are dropped.
- **Frontend:** a language picker next to the theme toggle (EN · NL · ES · FR), per viewer, in `localStorage`. A translated card has the label *translated · checked*; a click shows the English original. Fixed UI texts come from a small dictionary, `frontend/lib/dictionary.ts` (no library).
- **Settings:** `ITG_LANGUAGES=nl,es,fr` (default; empty turns translation off). No right-to-left languages: they need layout work first. `MODEL_TRANSLATOR` for `github` and `foundry`; `FOUNDRY_TRANSLATOR_AGENT` / `FOUNDRY_TRANSLATOR_AGENT_VERSION` (`itg-translator` / `3`) for `foundry-agents`, published with `tools/create_foundry_agents.py --only translator`. `offline` gives a fixed "translation" (`[nl] …`) for tests.
- **Cost, measured on Foundry:** about 1.5–2.5 s after the English card and about 400–450 tokens per language for a moment card, about 1,300–1,500 tokens per language for a tactics card. The English card itself does not change.

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
| `ITG_LANGUAGES`, `FOUNDRY_TRANSLATOR_AGENT` / `FOUNDRY_TRANSLATOR_AGENT_VERSION` | `nl,es,fr`, `itg-translator` / `3` (see *Languages*) |
| Identity | system-assigned managed identity with *Cognitive Services User* on the Foundry resource |
