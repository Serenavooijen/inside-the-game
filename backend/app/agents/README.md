# Agents (slimme rijstrook)

Maakt van een `FactSheet` een gecontroleerd `Insight` voor de frontend.

```
Statistician (code, Stats Engine)  →  Analyst (LLM)  →  Fact-checker (code)  →  Narrator (LLM, streaming)
        feiten met fact_id               2–3 claims        elk getal moet         1–3 zinnen voor de fan,
        en source_event_ids              met fact_ids      in een geciteerd       daarna nog een keer
                                                          feit staan             gecontroleerd
```

De Analyst en de Narrator zijn Microsoft Agent Framework-`Agent`s op een OpenAI-compatibele client. GitHub Models en Foundry gebruiken dus dezelfde code.

## Installeren

Vanuit `backend/`:

```bash
uv add agent-framework-core agent-framework-openai agent-framework-foundry azure-identity azure-ai-projects pydantic
uv add --dev pytest
```

Getest met `agent-framework-core` 1.22.0, `agent-framework-openai` 1.17.0 en `azure-ai-projects` 2.7.0. Voor de Foundry-pakketten: `uv` installeert de versies die bij `agent-framework-core` passen.

## Aanroepen (voor de Moment Detector)

```python
from app.agents import run_workflow

insight = await run_workflow(moment, factsheet, on_update, generation=gen)
```

- **`on_update(insight)`** wordt aangeroepen bij elke tussenstap: eerst `phase="analysing"`, daarna `"streaming"` met een groeiende `text`, en als laatste de eindversie. Stuur elke update als SSE-bericht `insight` door. Dat mag een gewone of een async functie zijn.
- **Timeout:** de workflow bewaakt zelf een deadline (`AGENT_DEADLINE_S`, standaard 6 s) en geeft **altijd** een `Insight` terug. Bij een timeout, een modelfout of als geen enkele claim de check haalt, krijg je `status="fallback"` met een `fallbackReason` en een template-tekst uit de feiten. Zet er als vangnet `asyncio.wait_for(..., 8)` omheen.
- **JSON voor de frontend:** `insight.to_json()` geeft camelCase (`momentId`, `fallbackReason`, `citedFactIds` …), precies zoals `frontend/lib/contracts.ts`.
- **Statussen:**
  - `checked`: alles klopt;
  - `corrected`: minstens één claim is afgekeurd. Die staat in `claim` en `rejectedClaims`, en de tekst bevat alleen goedgekeurde claims;
  - `fallback`: zie hierboven.

## Model kiezen

| `MODEL_PROVIDER` | Waar de agents staan | Waar de modellen draaien | Nodig |
| --- | --- | --- | --- |
| `github` | in deze code | GitHub Models | `GITHUB_TOKEN` (PAT met `models:read`) |
| `foundry` | in deze code | jouw Foundry-project | `FOUNDRY_PROJECT_ENDPOINT` + `az login` |
| `foundry-agents` | in Foundry Agent Service, zichtbaar in de portal | jouw Foundry-project | eerst `tools/create_foundry_agents.py` draaien |
| `offline` | geen model | – | niets |

Zonder `MODEL_PROVIDER` wordt het `github` als `GITHUB_TOKEN` bestaat, anders `offline`.

Overige instellingen:

| Variabele | Betekenis |
| --- | --- |
| `MODEL_ANALYST`, `MODEL_NARRATOR` | modelnamen; op Foundry de namen van je deployments. Standaard `openai/gpt-4.1-mini` / `openai/gpt-4.1-nano` op GitHub Models, `gpt-4.1-mini` voor beide op Foundry |
| `FOUNDRY_PROJECT_ENDPOINT` | Foundry-portal → je project → Overview → endpoint, bijvoorbeeld `https://<resource>.services.ai.azure.com/api/projects/<project>` |
| `FOUNDRY_ANALYST_AGENT`, `FOUNDRY_NARRATOR_AGENT` | namen van de gehoste agents, standaard `itg-analyst` / `itg-narrator` |
| `FOUNDRY_ANALYST_AGENT_VERSION`, `FOUNDRY_NARRATOR_AGENT_VERSION` | versie van de gehoste agents; het setupscript schrijft die naar `backend/.env.foundry-agents` |
| `AGENT_DEADLINE_S` | standaard `6` |

Controleer de modelnamen in de catalogus van GitHub Models. Die verandert weleens.

## Inloggen en opwarmen (Foundry)

- **Op je laptop** gebruikt de code direct de Azure CLI (`az login`). `DefaultAzureCredential` probeert eerst andere methoden en verliest daar seconden mee. Wil je die toch, zet dan `AZURE_CREDENTIAL=default`.
- **In Azure Container Apps** wordt automatisch de managed identity gebruikt.
- **Opwarmen:** het eerste token ophalen kost een paar seconden. Roep daarom bij het opstarten één keer `await model.warmup()` aan, in de FastAPI-lifespan. `run_fixtures` doet dat zelf en telt die tijd niet mee.
- **Echte latency meten:** `run_fixtures --deadline 30` geeft geen fallback op tijd, zodat je ziet hoe lang een moment echt duurt.

## Foundry: agents in code tegenover agents in Foundry Agent Service

Je kunt de twee opzetten naast elkaar testen. Ze gebruiken dezelfde instructies, hetzelfde outputschema, dezelfde fact-check en dezelfde fallback. Het enige verschil is waar de agent woont.

- **`foundry`:** de instructies en het schema staan in `prompts.py` en `models.py` en gaan bij elke aanroep mee. Foundry levert alleen het model.
- **`foundry-agents`:** de Analyst en de Narrator zijn prompt agents in Foundry Agent Service. Je ziet ze in de portal, met versies. Instructies, model en schema staan in Foundry; de code verwijst alleen naar de naam en de versie.

**Eenmalig opzetten**

1. Zet in je Foundry-project een model-deployment `gpt-4.1-mini` klaar. De Analyst en de Narrator gebruiken allebei dit model (voor `gpt-4.1-nano` was geen quotum).
2. Zorg dat je account de rol **Azure AI User** heeft op het project. Log in met `az login`.
3. Maak de gehoste agents aan (PowerShell, vanuit `backend/`):
   ```powershell
   $env:FOUNDRY_PROJECT_ENDPOINT = "https://<resource>.services.ai.azure.com/api/projects/<project>"
   $env:MODEL_ANALYST = "gpt-4.1-mini"
   $env:MODEL_NARRATOR = "gpt-4.1-mini"
   uv run python tools/create_foundry_agents.py
   ```
   Elke run maakt een nieuwe versie. Pas je de prompts aan, draai dit script dan opnieuw, anders blijven de gehoste agents op de oude tekst.

**Vergelijken**

```powershell
uv run python -m app.agents.run_fixtures --compare foundry,foundry-agents
uv run python -m app.agents.run_fixtures --compare github,foundry,foundry-agents --json vergelijking.json
```

Per opzet zie je de totale latency (p50 en p95), de tijd tot de eerste tekst, het aantal tokens en hoeveel momenten `checked`, `corrected` of `fallback` werden. Per moment staan de teksten onder elkaar.

Waar je op kunt letten:

- **Snelheid:** de tijd tot de eerste tekst bepaalt hoe vlot de uitleg in beeld komt. Het totaal moet onder de 6 seconden blijven.
- **Kwaliteit:** halen de claims de fact-check? Zijn de teksten even goed?
- **Beheer en zichtbaarheid:** gehoste agents staan in de portal met versies en traces. Dat is mooi voor de jury, maar een promptwijziging vraagt dan om een nieuwe versie.

## Testen

```bash
# 1. FactSheets maken van de echte wedstrijd (eenmalig, na het draaien van de generator)
uv run python tools/build_test_moments.py ../output ../script/match_script.json

# 2. Workflow draaien op alle testmomenten
uv run python -m app.agents.run_fixtures
uv run python -m app.agents.run_fixtures --inject-wrong   # laat zien dat de checker een fout getal tegenhoudt
uv run python -m app.agents.run_fixtures goal-24 red-53   # alleen deze momenten

# 3. Unit tests, zonder token of netwerk
uv run pytest tests/agents -q
```

De tests draaien de echte Agent Framework-code tegen een nep-OpenAI-server (`tests/agents/fake_openai.py`). Zo worden structured output, streaming en de timeout getest zonder krediet te gebruiken.

## Testmomenten (`fixtures/moments/`)

Acht momenten uit de referentiewedstrijd (seed 8002):

- de gele kaart van Quiroga (13');
- de vier goals (24', 39', 68', 82');
- de rust;
- de rode kaart van Brannigan (53');
- het moment tien minuten na de rode kaart (63').

Elk feit is berekend uit `events.json`, `tracking.csv` en `stats_per_minute.json`. De Stats Engine van Bryan gaat deze FactSheets straks live maken, in dezelfde vorm.

## Nog te doen

- **Echte modellen:** draaien met `github`, `foundry` en `foundry-agents`, de uitkomsten vergelijken en een keuze maken voor de demo.
- **Contract:** zodra Bryans `contracts.py` op `main` staat, `models.py` daarop laten aansluiten en de dubbele modellen hier weghalen.
- **Tracing:** naar Application Insights (OpenTelemetry). Agent Framework ondersteunt dat.
