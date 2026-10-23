# Overdracht: de agents koppelen aan de backend

**Voor:** Bryan · **Van:** Serena · 22 okt 2026

De slimme rijstrook staat klaar in `backend/app/agents/`. Je hebt er één functie voor nodig, `run_workflow()`. Die krijgt een moment en een FactSheet en geeft altijd een `Insight` terug, binnen 6 seconden. Deze notitie legt uit wat de backend daarvoor moet doen.

## 1. Wat er nu staat

- **De workflow:** Analyst (LLM) → fact-checker (code) → Narrator (LLM, streaming) → nog een controle op de tekst van de Narrator.
- **Waar het draait:** Microsoft Foundry, project `svanooijen-7451` (West Europe), model `gpt-4.1-mini`.
- **Twee opzetten**, met één schakelaar `MODEL_PROVIDER` en verder dezelfde code:
  - `foundry`: agents in code. Handig tijdens het ontwikkelen.
  - `foundry-agents`: gehoste agents `itg-analyst` en `itg-narrator` in Foundry Agent Service. **Dit gebruiken we in de demo.**
  - `offline`: zonder model, met vaste teksten. Voor tests en CI.
- **Gemeten op de 8 testmomenten:** alle 8 checked, p50 ongeveer 4 s, p95 ongeveer 5 s.
- **Tests:** `uv run pytest tests/agents -q` (20 tests, zonder netwerk).
- Alle details staan in `backend/app/agents/README.md`.

## 2. Aanroepen vanuit FastAPI

```python
# backend/app/main.py (schets)
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.agents import run_workflow, FactSheet, Moment
from app.agents.llm import model_from_env

agent_model = model_from_env()            # leest MODEL_PROVIDER en de andere variabelen
smart_lane = asyncio.Semaphore(2)         # maximaal 2 momenten tegelijk
tasks: set[asyncio.Task] = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await agent_model.warmup()            # token ophalen + verbinding openen (4–9 s, één keer)
    yield

app = FastAPI(lifespan=lifespan)


async def on_moment(moment: Moment, factsheet: FactSheet, generation: int) -> None:
    """De Moment Detector roept dit aan. Blokkeer de snelle rijstrook nooit: start een taak."""

    async def publish(insight):
        if insight.generation != bus.generation:   # na een seek: oude resultaten weggooien
            return
        await bus.publish("insight", insight.to_json())

    async def job():
        async with smart_lane:
            await asyncio.wait_for(
                run_workflow(moment, factsheet, publish, generation=generation, model=agent_model),
                timeout=8,  # vangnet; de workflow heeft zelf al een deadline van 6 s
            )

    t = asyncio.create_task(job())
    tasks.add(t)
    t.add_done_callback(tasks.discard)


def on_seek() -> None:
    """Bij een seek: lopende agenttaken stoppen, want hun resultaten horen bij een oude generation."""
    for t in list(tasks):
        t.cancel()
```

`bus` is jouw EventBus. Hoe je hem precies noemt maakt niet uit, zolang `publish("insight", …)` als SSE-bericht `insight` naar de frontend gaat.

## 3. De SSE-berichten

`on_update` wordt per moment een paar keer aangeroepen. Stuur elke update door, de frontend werkt de kaart dan bij via `id`:

| Fase | Wat de frontend ziet |
| --- | --- |
| `phase: "analysing"` | een kaart met "analyseren…" |
| `phase: "streaming"` | `text` groeit woord voor woord |
| `phase: "done"` | de eindversie, met `status`, `evidence` en eventueel `claim` en `rejectedClaims` |

Voorbeeld van de eindversie (`insight.to_json()`, camelCase, zoals `frontend/lib/contracts.ts`):

```json
{
  "id": "i-goal-68", "t": 4146, "minute": "68", "momentId": "goal-68",
  "type": "goal", "team": "ngr", "phase": "done", "status": "checked",
  "text": "Diallo-Kerr scores just 4 minutes after coming on, finishing a move featuring three players and a key through ball by Halvorsen.",
  "evidence": ["Diallo-Kerr (20) came on at 64', 4 minutes before this goal", "..."],
  "citedFactIds": ["F3", "F4"], "generation": 3, "latencyMs": 3526, "tokens": 658
}
```

- **`status: "checked"`:** alle getallen en namen komen uit de feiten.
- **`status: "corrected"`:** minstens één claim is weggelaten. Die staat in `claim` en `rejectedClaims`, met een reden. Toon dit in de UI als **"niet controleerbaar, weggelaten"** en niet als "fout": de claim kan inhoudelijk kloppen, maar we konden hem niet narekenen.
- **`status: "fallback"`:** het model was te traag of gaf een fout. Er staat dan een vaste tekst uit de feiten, met de reden in `fallbackReason`. De wedstrijd loopt gewoon door.

## 4. Wat de Stats Engine moet leveren

De FactSheet heeft dezelfde vorm als de testmomenten in `fixtures/moments/*.json`. Kijk daar voor voorbeelden. Dit model staat in `app/agents/models.py`. Zodra jouw `contracts.py` op `main` staat, laten we dat ene model gebruiken.

**Belangrijk: zet afgeleide getallen in de feiten zelf.** De checker laat alleen getallen door die letterlijk in een geciteerd feit staan. Laat de Stats Engine daarom ook de getallen leveren die een analist zou uitrekenen. Anders wordt een goede claim afgekeurd.

| Niet alleen dit | Maar dit |
| --- | --- |
| `Diallo-Kerr (20) came on at 64'` | `Diallo-Kerr (20) came on at 64', 4 minutes before this goal` |
| `The move: A → B → C → D` | `The move (3 players, 4 actions): A → B → C → D` |
| `Possession: 57% → 34%` | ook het verschil, als dat het verhaal is: `a drop of 23 points` |

Nog een paar regels:

- **`headline`:** een neutrale zin met de namen van de betrokken spelers, bijvoorbeeld `Goal Northgate: Diallo-Kerr (20), assist Halvorsen (18). Kingsbridge 1-2 Northgate`. Namen in de headline mag de Narrator altijd gebruiken.
- **`factId`:** `F1`, `F2` … per FactSheet. Zet het belangrijkste feit eerst, want de fallback gebruikt het eerste feit.
- **`sourceEventIds`:** de event-id's uit `events.json`. Die maken het "evidence"-verhaal voor de jury traceerbaar.
- **Aantal:** houd een FactSheet kort, 3–6 feiten. Elk extra token kost latency.

## 5. Instellingen in Azure Container Apps

Zet deze omgevingsvariabelen op de Container App:

```
MODEL_PROVIDER=foundry-agents
FOUNDRY_PROJECT_ENDPOINT=https://svanooijen-7451-resource.services.ai.azure.com/api/projects/svanooijen-7451
FOUNDRY_ANALYST_AGENT=itg-analyst
FOUNDRY_ANALYST_AGENT_VERSION=<uit backend/.env.foundry-agents>
FOUNDRY_NARRATOR_AGENT=itg-narrator
FOUNDRY_NARRATOR_AGENT_VERSION=<uit backend/.env.foundry-agents>
AGENT_DEADLINE_S=6
```

- **Inloggen:** zet een **system-assigned managed identity** aan op de Container App. Geef die de rol **Cognitive Services User** op de resource `svanooijen-7451-resource`. De code ziet zelf dat hij in Azure draait en gebruikt dan de managed identity. Er zijn dus geen sleutels nodig.
- **Geen secrets in de repo.** `.env` en `.env.foundry-agents` staan in `.gitignore`.
- **Promptwijziging?** Draai dan `uv run python tools/create_foundry_agents.py`. Dat maakt een nieuwe versie van de gehoste agents. Zet het nieuwe versienummer daarna op de Container App.

## 6. Bekende beperkingen

- **De checker controleert getallen en namen, niet de betekenis.** Een getal dat wel in de feiten staat maar bij het verkeerde gebeurtenis wordt gezet, glipt erdoor. Een keer schreef de Analyst bijvoorbeeld "red card at 63 minutes", terwijl de rode kaart in de 53e minuut was. Hetzelfde geldt voor bijvoeglijke naamwoorden, zoals "moderate xG" bij 0,09.
- **Latency:** p95 is ongeveer 5 s, dicht bij de 6 s. Op 10× snelheid kunnen twee momenten elkaar overlappen. Daarom staat de semaphore op 2, en het quotum van 50K TPM is daar ruim genoeg voor.
- **Voor de demo:** zorg voor een vaste opgenomen replay waarin zeker één afgekeurde claim zit. Het model maakt niet elke run een fout. `run_fixtures --inject-wrong` laat de correctie altijd zien.

## 7. Zelf proberen

```powershell
cd backend
az login
uv run python -m app.agents.run_fixtures --provider offline              # zonder Azure
uv run python -m app.agents.run_fixtures --provider foundry-agents       # echt, 8 momenten
uv run python -m app.agents.run_fixtures --provider foundry-agents --inject-wrong goal-24
```

Voor `foundry-agents` heb je de rol **Cognitive Services User** op de resource nodig. Vraag Serena die toe te wijzen.
