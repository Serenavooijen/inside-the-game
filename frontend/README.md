# Inside the Game – frontend

Next.js (App Router) + TypeScript + Tailwind CSS. De UI is in het Engels.

## Starten

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000.

- `/`: Pick a match
- `/match/kba-ngr`: live, met de AI-teksten die verschijnen terwijl ze gemaakt worden
- `/match/kba-ngr?replay=1`: een opgenomen run, zonder live AI

## Waar komt de data vandaan?

Alle data loopt via één hook: `lib/useMatchStream.ts`. De bron stel je in met `NEXT_PUBLIC_API_URL`:

| Waarde | Bron |
| --- | --- |
| `/api/mock` (standaard) | De ingebouwde mock-backend in `app/api/mock/[...path]/route.ts`. Die speelt `data/matches/kba-ngr.json` af en stuurt echte SSE. |
| `http://localhost:8000` | De echte FastAPI-backend. |

De mock en de echte backend gebruiken **dezelfde endpoints en berichten**. Overstappen is dus alleen een andere URL. Zet bij de echte backend CORS aan voor `http://localhost:3000`.

### Endpoints

| Methode | Pad | Body |
| --- | --- | --- |
| GET | `/matches` | |
| POST | `/match/load` | `{ "match_id": "kba-ngr", "mode": "live" \| "replay" }` |
| POST | `/play`, `/pause` | |
| POST | `/speed` | `{ "factor": 1 \| 10 }` |
| POST | `/seek` | `{ "t": 4138 }` (frame) |
| GET | `/state` | geeft een `MatchState` |
| GET | `/stream` | SSE |

### SSE-berichten

Elk bericht is `event: <type>` + `data: <json>`. De vormen staan in `lib/contracts.ts`. **Houd de Pydantic-modellen van de backend daar veld voor veld mee gelijk.**

| `event:` | Inhoud | Wanneer |
| --- | --- | --- |
| `tick` | `Tick`: frame, stand, xG, balbezit, tempo, `generation`, `keyMomentId` | elke nieuwe wedstrijdseconde |
| `overlay` | `Overlay` (`tag`, `pass`, `shot`, `sprint`) | snelle rijstrook, direct |
| `event` | `MatchEvent` (goal, kaart, wissel) | op het moment zelf |
| `insight` | `Insight` | meerdere keren per id: `analysing` → `streaming` (groeiende tekst) → `done` |
| `state` | `MatchState` | na (her)verbinden en na een seek |

### Afspraken met de backend

- **De backend is de baas over de tijd.** De frontend houdt geen eigen klok bij; hij interpoleert alleen vloeiend tussen twee frames.
- **Seek verhoogt `generation`.** De frontend gooit overlays en inzichten met een oudere `generation` weg.
- **Key moment:** bij een event met `key: true` zet de backend het tempo op 1× en vult `keyMomentId` in de tick. Zodra het inzicht klaar is en ongeveer 7 seconden in beeld stond, maakt de backend `keyMomentId` weer `null` en zet het tempo terug. De frontend schuift de kaart dan naar de feed.
- **Fallback:** komt er na 6 s geen modeltekst, dan stuurt de backend het inzicht met `status: "fallback"` en een `fallbackReason`.
- **Reconnect:** `EventSource` maakt zelf opnieuw verbinding. Daarna roept de frontend `GET /state` aan.

## Data: de echte generator

`data/matches/kba-ngr.json` komt uit `generate_match.py` (seed 8002), omgezet door `scripts/import_generator.py`. Opnieuw maken na een wijziging in het draaiboek:

```bash
# in de hoofdmap van de repo
python generator/generate_match.py            # schrijft output/
cd frontend
npm run fixture                               # = python scripts/import_generator.py ../output ../script/match_script.json
```

Wat echt is en wat niet:

| Onderdeel | Bron |
| --- | --- |
| Posities, bal, events, stand, wissels, kaarten | generator (`tracking.csv`, `events.json`) |
| xG, balbezit, schoten | generator (`stats_per_minute.json`, shots) |
| Sprints | snelheden uit `tracking.csv` (drempel 23,8 km/u) |
| Shot-overlay | toont xG; de generator heeft geen schotsnelheid |
| **Pass quality** | **placeholder** uit passlengte en terreinwinst. Vervangen door het pass-difficulty-model van de Stats Engine. |
| Inzichtteksten | opgenomen "agent-output" voor de demo: verhaal uit het draaiboek, alle cijfers berekend uit de generator |

De tijd `t` is het generator-frame: seconden spel sinds de aftrap, inclusief blessuretijd (0–5821). De backend stuurt daarnaast `clock` ("45+1:30") en `minute` ("45+2") mee. De rust ligt op `halftime` (frame 2821). In de tweede helft speelt Kingsbridge naar links, net als in de generator.

### Line-ups, spelersanalyse en corners

`data/lineups/kba-ngr.json` komt uit `scripts/build_lineups.py` (na `npm run fixture`):

```bash
python scripts/build_lineups.py               # leest ../output, ../script/match_script.json, ../output/cup en data/matches/kba-ngr.json
```

Alles is door code gemeten, zonder AI. De frontend snijdt het bestand af op de huidige wedstrijdseconde (`lib/lineups.ts`). Daardoor werkt het met de mock en met de echte backend, live en na een seek, zonder contractwijziging. Het bestand laadt in een eigen chunk.

| Onderdeel | Bron en definitie |
| --- | --- |
| Rollen, formaties | `tactical_states.json`; bankspelers uit de selectie in het draaiboek |
| Touches | alle balacties van de speler in `events.json` (pass, cross, aanname, schot, take-on, tackle, clearance, interceptie, herovering, spelhervatting, redding, blok) |
| Passes | pass + cross, compleet / totaal |
| Duels | tackles en take-ons, van beide kanten |
| Recoveries | ball_recovery + interception |
| Sprints, afstand, topsnelheid | snelheid uit `tracking.csv` (sprint ≥ 23,8 km/u); afstand per 10 s |
| Gemiddelde positie, heatmap | posities elke 5 s, teamrelatief: het team valt altijd van links naar rechts aan |
| Corners | het frame bij de voorzet, de eerste balcontact en de uitkomst; opgeslagen als corner van links (u langs de doellijn, v vanaf de doellijn). Een corner die niet genomen is (59', wissel) telt niet mee. Lengtes uit `player_profiles` in `script/pre_match_context.json`; de kaart toont ze alleen in de zestien. |

De namen, rollen en wissels komen uit de eventdata. Waar de ontwerp-prompt afwijkt (bijvoorbeeld Achterberg valt in op 59', Okafor-Hale en Visser gaan eraf op 76'), volgt de app de data.

## Keuzes die afwijken van de ontwerp-prompt

- **"Corrected" in plaats van "VAR · Overturned".** Het gaat om een AI-uitspraak die de fact-checker heeft verbeterd, niet om een scheidsrechtersbeslissing. Daarom is de status in het contract `corrected`.
- **Fonts via `@fontsource`** in plaats van `next/font/google`. Ze zitten dan in het npm-pakket, dus de build heeft geen internet nodig. Dat is handig in Azure en in CI.
- **Tailwind 3.4** met `tailwind.config.ts`, zoals in het design.

## Mappen

```
app/                     routes: /, /match/[id], /api/mock/*
components/              Scorebar, Pitch, OverlayLayer, InsightCard, ProducerFeed, KeyMoment, Controls
lib/contracts.ts         het contract met de backend
lib/useMatchStream.ts    de enige plek die met de backend praat
lib/useInterpolatedFrame.ts  vloeiende beweging tussen frames
lib/mock/engine.ts       de mock-backend
data/matches/            de opgenomen wedstrijd
design/                  de prototypes uit Claude Design (referentie, geen productiecode)
scripts/import_generator.py  zet de generator-uitvoer om naar de opname
scripts/build_lineups.py     line-ups, spelercijfers, posities en corners (data/lineups/)
```
