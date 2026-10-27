# Agents (slimme rijstrook)

Maakt van een `FactSheet` een gecontroleerd `Insight` voor de frontend.

```
Statistician (code, Stats Engine)  →  Analyst (LLM)  →  Fact-checker (code)  →  Narrator (LLM, streaming)
        feiten met fact_id               2–3 claims        elk getal moet         1–3 zinnen voor de fan,
        en source_event_ids              met fact_ids      in een geciteerd       daarna nog een keer
                                                          feit staan             gecontroleerd
```

De Analyst en de Narrator zijn Microsoft Agent Framework-`Agent`s op een OpenAI-compatibele client. GitHub Models en Foundry gebruiken dus dezelfde code.

Met `TACTICS_ENABLED=1` komt er een derde agent bij, de **Scout** (tactische analyse), en maakt de Narrator elke minuut één commentaarzin. Zie [Tactische analyse](#tactische-analyse-de-scout).

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

## Tactische analyse: de Scout

De blik van een opposition analyst: hoe bouwt een team op, hoe hoog staat de linie, welke flank, wat veranderde er door een wissel, en wijkt het af van de bekerwedstrijd? En vooral: wat betekent het?

```
Tactician (code, app/tactics.py)  →  Scout (LLM)  →  Fact-checker (code)
  tactische feiten per venster,        2–3 observaties,    observatie: check_claim
  één detector per playbook-concept    elk met gevolg en   gevolg en coach-actie: check_text + unknown_names
  + de bekerbaseline (C-feiten)        coach-actie         (geen nieuwe getallen of namen)
```

**De code meet, het model interpreteert.**

- **Tactician:** `app/tactics.py` implementeert de detectors uit [`knowledge/tactics_playbook.md`](knowledge/tactics_playbook.md): B1 B2 B3 B5 B6, P1 P2, D1 D2 D3, T1 T3 en G1 G2 G3.
  - Een detector levert alleen een feit als het signaal betekenisvol is, of als het veranderd is ten opzichte van het vorige venster of de beker.
  - Vergelijkingen en verschillen staan al in de tekst van het feit, bijvoorbeeld `(previous 5 minutes: 31%; cup match: 58%, down 58 points)`.
  - Blokhoogte en compactheid (D1, D2, ook in G2 en G3) worden alleen gemeten als de tegenstander de bal in het middenstuk heeft (35–70 m van het eigen doel). Over alle frames zegt de linie vooral waar de bal was: een diepe bal trekt hem naar 10–13 m. Met de bal in het middenstuk zie je de keuze van het team, en kun je wedstrijden eerlijk vergelijken.
- **Scout:** `scout.py` en `run_scout()` geven een `Insight` van type `"tactics"` met `observations`, `heatmap` en `buildUp`.
  - De Scout krijgt alleen de regels van de concepten waarvan de detector vuurde, één regel per concept (`playbook.py`), nooit het hele playbook.
  - Conceptnamen en tactische termen ("Far-side", "the 6", "back three", "three up front") gelden niet als verzonnen naam of getal.
- **Labels, richting en stand komen uit de code:**
  - vaste labels (`BANDS` in `tactics.py`): PPDA *very intense / intense / moderate / passive pressing*, blokhoogte *low / mid / high block*, compactheid *compact / medium / stretched*;
  - de richting staat in woorden in de tekst ("8 m deeper than the cup match", "5 m more compact than the previous 5 minutes");
  - de stand is een feit, aan het eind van elk venster en voor elke wissel of formatiewijziging ("At 64' Northgate were level at 1-1, 11 v 10");
  - PPDA alleen bij minimaal 5 verdedigende acties.
- **Controle:**
  - Een observatie valt weg, met de reden erbij, bij een getal dat niet in de geciteerde feiten staat, bij een uitspraak over de stand die geen standfeit toelaat, of bij een vergelijkend woord dat de feiten tegenspreekt ("less compact" waar de feiten "more compact" zeggen).
  - Een gevolg met nieuwe getallen of namen laat de hele observatie wegvallen.
  - Een afgekeurde coach-actie valt alleen zelf weg. Dat gebeurt ook als hij het advies van de vorige analyse herhaalt.
  - `compareToCup` wordt `n/a` als geen geciteerd feit de beker noemt.
- **De vorige analyse** gaat mee als context. De instructie is: alleen nieuw of veranderd advies.
- **Harde deadlines:** alle model-aanroepen, ook die voor de momentkaarten, lopen via `deadline.within()`. Die komt op tijd terug, ook als een geannuleerde aanroep blijft hangen.
- **Wanneer:** elke 5 minuten speeltijd en bij de rust (`app/scout_lane.py`). Bij elke wissel komen twee kaarten van type `"substitution"`: direct "what to watch" (code, zonder model), en 8 minuten later "impact" (de Scout op de `SubstitutionFactSheet` van `Tactician.substitution_sheet()`). Er draait er hoogstens één tegelijk, met een eigen deadline van 15 s. Een seek gooit alles weg. Bij een timeout of fout komen er template-observaties uit feiten plus playbook, met status `fallback`.
- **Scoutingrapport:** `tools/build_scouting_report.py` laat de Scout vooraf de bekerwedstrijd (`script/cup/`, `output/cup/`) beschrijven en schrijft `fixtures/scouting/kba-ngr-cup.json`.
  - De feiten C1 … C30 zijn tegelijk de baseline voor elke live analyse.
  - De backend laadt het rapport bij de wedstrijd en stuurt het mee als `MatchState.scouting`.

**Narrator per minuut** (`commentary.py`, `app/commentary_lane.py`):
- Elke minuut maakt de code een kleine FactSheet: de belangrijkste actie, het balbezit in die minuut, de stand en de feitregels van de laatste tactische kaart.
- De Narrator maakt daar één zin van, maximaal 25 woorden.
- De zin gaat door `check_text` en `unknown_names` en daarna als SSE-bericht `commentary` naar de frontend.
- Afgekeurd, te lang of later dan 5 s: dan blijft de minuut stil.
- **Bekende beperking:** op Foundry en 10× snelheid blijven de meeste minuten stil. Gemeten tot 54': 10 regels zonder vertaling (`ITG_LANGUAGES=` leeg), 11 met `nl,es,fr`. De regels die er komen zijn op tijd, 0,2 wedstrijdminuut na hun minuut. De balk toont de laatste regel die er was, dus op 30' kan dat die van 23' zijn. De vertaling is niet de oorzaak; die komt na de Engelse regel en houdt hem niet op.

| Variabele | Betekenis |
| --- | --- |
| `TACTICS_ENABLED` | `1` zet de Scout, het scoutingrapport en het commentaar per minuut aan. Zonder de vlag verandert er niets. |
| `MODEL_SCOUT` | modelnaam voor de Scout bij `github` en `foundry`, standaard `gpt-4.1-mini` |
| `FOUNDRY_SCOUT_AGENT`, `FOUNDRY_SCOUT_AGENT_VERSION` | de gehoste Scout, standaard `itg-scout`, nu versie 3. Zonder versie werkt de rest gewoon, en krijgen de tactische kaarten de fallback. |
| `SCOUT_DEADLINE_S` | standaard `15` |
| `COMMENTARY_DEADLINE_S` | standaard `5` |
| `ITG_SCOUTING_REPORT` | pad naar het rapport, standaard `fixtures/scouting/kba-ngr-cup.json` |

Zelf proberen:

```powershell
uv run python -m app.agents.run_scout --provider offline          # 5 vensters, de rust en de wissels van 64'
uv run python -m app.agents.run_scout --provider foundry-agents
uv run python tools/create_foundry_agents.py --only scout          # alleen itg-scout publiceren
uv run python tools/build_scouting_report.py --provider foundry-agents
```

Gemeten met `itg-scout` v3 (gpt-4.1-mini) op 5 vensters, de rust en de wissels van 64': alle 7 analyses `checked`, 4,5–5,6 s per analyse.

## Talen: de Translator

Eerst controleren, dan vertalen, dan opnieuw controleren (`translator.py`, `app/translation_lane.py`):

1. De bestaande workflow maakt de Engelse kaart, zoals altijd.
2. Is de kaart klaar en `checked` of `corrected`? Dan vertaalt de **Translator** (`itg-translator`) alleen die tekst, per taal, in brokken van 3 teksten tegelijk. Hij wacht zolang er een moment geanalyseerd wordt.
3. `check_translation` (`checker.py`) vergelijkt elke vertaalde tekst met de Engelse bron: dezelfde getallen (ook telwoorden van de doeltaal, 0,41 = 0.41), dezelfde namen en geen nieuwe, hoogstens ongeveer twee keer zo lang.
4. Dezelfde kaart gaat nog een keer de deur uit, met `translations`. Afgekeurd of later dan 6 s: `rejected` met een reden, en de UI toont Engels met het label EN. Elke afgekeurde vertaling komt in het log, met bron en vertaling.

| Variabele | Betekenis |
| --- | --- |
| `ITG_LANGUAGES` | standaard `nl,es,fr`; leeg zet het uit. Geen talen van rechts naar links. |
| `MODEL_TRANSLATOR` | modelnaam bij `github` en `foundry`, standaard `gpt-4.1-mini` |
| `FOUNDRY_TRANSLATOR_AGENT`, `FOUNDRY_TRANSLATOR_AGENT_VERSION` | de gehoste Translator, standaard `itg-translator`, nu versie 3. Zonder versie blijft alles Engels. |
| `TRANSLATE_DEADLINE_S`, `SCOUTING_TRANSLATE_DEADLINE_S` | standaard `6` en `30` (het scoutingrapport, bij het laden) |

```powershell
uv run python tools/create_foundry_agents.py --only translator     # alleen itg-translator publiceren
```

Gemeten met `itg-translator` v3 op Foundry: de goal van 24' in alle drie talen `checked`, 1,5–2,5 s na de Engelse kaart, ongeveer 400–450 tokens per taal; een tactiekkaart ongeveer 2,2–2,6 s en 1.300–1.500 tokens per taal.

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
- **Overige detectors:** B4, P3–P7, D4–D6, T2, T4, S1–S2 en G4 uit het playbook. De Scout kan ze pas noemen als hun detector bestaat.
- **Betekenis van een gevolg:** de checker houdt nieuwe getallen en namen tegen, maar niet een gevolg dat de verkeerde kant op redeneert, zoals "less intense" bij een lagere PPDA. Een steekproef per demo-run blijft nodig.
