# Architectuur Inside the Game

Oct 12, 2026 · @Serena

## In het kort

We zetten een synthetische voetbalwedstrijd om in uitlegbare match intelligence. Die verschijnt live als overlays naast de wedstrijd. Het systeem bestaat uit drie delen: een offline voorbereiding die wedstrijden maakt, één backend die de wedstrijd afspeelt en analyseert, en een Next.js-frontend die alles toont.

Het kernidee is een backend met **twee rijstroken**:

- **Snelle rijstrook (< 100 ms, deterministisch):** elk event gaat direct door de Stats Engine en wordt meteen een overlay, zoals een spelertag, passkwaliteit, schotsnelheid of sprint. Hier zit geen LLM in.
- **Slimme rijstrook (2–6 s, agents):** bij een sleutelmoment of elke 5 wedstrijdminuten legt een multi-agent workflow uit wat er gebeurt en waarom het ertoe doet.

Zo blijft het beeld vloeiend, terwijl de diepere duiding een paar seconden later volgt.

## Overzicht

&#91;embedded content: architectuur · voorbereiding, backend, frontend\]

De draaiboekagent maakt vooraf de wedstrijden. Tijdens het afspelen splitst de Stats Engine de stroom: live metrics gaan direct naar de Overlay Composer, sleutelmomenten gaan langs de agents. De besturing in de frontend stuurt de simulator via gewone HTTP-calls.

## Voorbereiding: wedstrijden maken

Er wordt geen data aangeleverd, dus we maken onze eigen wedstrijden. Dat gebeurt offline, vóór de wedstrijd, in vijf stappen:

1. **Scenario-prompt:** je geeft de teams, de speelstijl, het verloop en de plotwendingen op.
2. **Draaiboekagent:** schrijft daaruit een draaiboek met spelers, formaties, fases en tijdlijn. Hij draait op Microsoft Agent Framework met een model via Foundry of GitHub Models.
3. **Validatie:** controleert het JSON-schema en de consistentie (stand, kaarten, wissels). Bij een fout gaat het draaiboek terug naar de agent.
4. **Draaiboek-bibliotheek:** bewaart per wedstrijd een `match_script.json` en een `pre_match_context.json` in Blob Storage.
5. **Generator:** `generate_match.py` speelt het draaiboek af als 1 Hz-simulatie, met een vaste seed per wedstrijd. Dezelfde seed geeft altijd dezelfde wedstrijd.

De eerste wedstrijd staat al klaar: Kingsbridge Athletic – Northgate Rovers (2-2, seed 8002). Met de draaiboekagent kunnen we snel meer wedstrijden maken om de demo en de agents te testen.

## Backend: één FastAPI-container

De hele backend draait als één FastAPI-container op Azure Container Apps. Alle onderdelen zijn asyncio-taken in hetzelfde proces, en de app start ze bij het opstarten.

| Onderdeel | Rijstrook | Wat het doet |
| --- | --- | --- |
| Match Simulator | – | Speelt de gegenereerde events af, met play, pause, tempo (standaard 10×) en seek naar een moment. |
| EventBus | – | Brengt events van de simulator naar alle onderdelen die luisteren, via `publish()` en `subscribe()`. Nu een `asyncio.Queue` in het geheugen, met een eigen queue per abonnee. |
| Stats Engine + MatchState | snel | Houdt de stand bij (stand, balbezit, xG, PPDA, field tilt, momentum) en berekent metrics per event: passafstand en -moeilijkheid, bal- en schotsnelheid, sprints. |
| Moment Detector | slim | Herkent sleutelmomenten met regels (goal, schot, kaart, wissel, balverlies in de gevarenzone, momentumomslag) en geeft elke 5 minuten een tick. |
| Agent Workflow | slim | Statistician → Analyst → Narrator → Fact-checker, gebouwd met Microsoft Agent Framework. Bij een fout volgt een retry of een template als fallback. De Personalizer komt erbij als er tijd is. |
| MCP-server "match-stats" | slim | Geeft de agents tools om de stats op te vragen: `get_state`, `get_player`, `get_window`, `compare_phases`, `get_pre_match_context`. |
| Overlay Composer | beide | Voegt de live stats en de inzichten van de agents samen tot Overlay JSON (`t_in`, `t_out`, `slot`, `priority`). |
| Run Recorder | – | Slaat elke run op als JSONL in Blob Storage. Daarmee werkt de replay-modus, ook als het Azure-krediet op is. |

De agents mogen de snelle rijstrook nooit ophouden. Elke agent-run start daarom als een losse taak, zodat de live overlays gewoon doorlopen.

Omdat alle state in het geheugen zit, draait de container met precies 1 worker en 1 replica.

## Frontend: Next.js

De frontend krijgt alle overlays binnen via één SSE-verbinding (Server-Sent Events) op `/stream`. Opdrachten zoals een wedstrijd kiezen, play, pause, tempo en seek gaan als gewone HTTP-calls terug naar de backend.

- **2D-veld + overlaylaag:** spelers als stipjes op het veld, met de overlays er getimed overheen.
- **Producer feed:** de lopende stroom van inzichten en commentaar van de agents.
- **Besturing:** wedstrijd kiezen, play, pause, tempo en "spring naar moment".
- **Fanmodus (fase 2):** dezelfde wedstrijd, aangepast voor een analist of een casual fan, voor een favoriete club of speler en in een gekozen taal.

## Azure-diensten en modellen

| Dienst | Waarvoor |
| --- | --- |
| Azure Container Apps | De backend, en de frontend als die niet op Static Web Apps Free komt. |
| Microsoft Foundry | Modellen voor de demo: kleine modellen voor de meeste agents, een groter model voor de Analyst. Ook de tracing van de agents. |
| Foundry Agent Service: `itg-translator` | De Translator (gpt-4.1-mini, gehost zoals `itg-analyst`, `itg-narrator` en `itg-scout`). Vertaalt alleen gecontroleerde Engelse kaarten naar NL, ES en FR. De code controleert elke vertaling opnieuw tegen de bron: dezelfde getallen en namen, een redelijke lengte. |
| GitHub Models | Gratis modellen tijdens de ontwikkeling. Je wisselt met één env var tussen GitHub Models en Foundry. |
| Application Insights | Traces van elke agent-run, via OpenTelemetry. |
| Blob Storage | De draaiboek-bibliotheek en de opgenomen runs. |
| Managed identity | Toegang tot Blob Storage en Foundry zonder sleutels in de code. |

Voor de demo stappen we over op Foundry met pay-as-you-go, met een budgetalert erop.

## Keuzes en waarom

| Keuze | Waarom |
| --- | --- |
| Twee rijstroken | Overlays moeten direct verschijnen, en een LLM doet er seconden over. Door ze te scheiden blijft het beeld vloeiend en komt de duiding er los bij. |
| Eén container met een queue in het geheugen | Simpel en snel genoeg voor een hackathon: er komt geen extra infrastructuur bij. De EventBus-interface houdt de weg open naar Event Hubs. |
| SSE in plaats van WebSockets | Het verkeer gaat vooral één kant op, van de server naar de browser. SSE is daarvoor eenvoudiger. |
| Eigen compact JSON-schema voor events | Sluit direct aan op onze generator. |
| Agents bij sleutelmomenten + elke 5 minuten | Duiding waar het ertoe doet, en daartussen regelmatige updates zonder dat de kosten oplopen. |
| Fact-checker als laatste stap | Elke uitspraak wordt tegen de stats gecontroleerd voordat hij in beeld komt. |
| Run Recorder + replay | De demo blijft werken, ook als het Azure-krediet op is of het model traag is. |
| Contracten op dag 1 vastleggen | MatchEvent, MatchState, Moment, FactSheet, Insight, Overlay en FanProfile. Zo kunnen de drie mensen parallel bouwen. |

### Waarom Azure Container Apps

Container Apps draait onze container zolang we willen, zonder dat we Kubernetes hoeven te beheren. We betalen alleen voor wat we gebruiken.

- **Een langlopend proces:** de simulator, de EventBus, de agent-taken en de open SSE-verbindingen leven in één proces dat continu draait.
- **Lokaal en in Azure hetzelfde:** één Docker-image, dus wat op een laptop werkt, werkt ook in Azure.
- **Weinig beheer:** HTTPS, een publieke URL, logging en managed identity zitten erin.
- **Goedkoop:** we betalen per gebruik en er zit een maandelijks gratis tegoed in.
- **Revisies:** elke deploy is een revisie, dus vlak voor de demo zetten we met één klik de vorige terug.
- **Jurering:** het telt mee voor "Best Azure Cloud Native Integration", en het groeipad (agents als losse apps, Event Hubs) is er makkelijk op uit te leggen.

| Alternatief | Waarom niet |
| --- | --- |
| App Service (container) | Werkt ook, maar heeft geen scale-to-zero en is minder cloud native. |
| Azure Functions | Past niet bij een proces dat continu draait, met state in het geheugen en open SSE-verbindingen. |
| AKS | Te zwaar voor één container en een team van drie. |
| Static Web Apps | Alleen geschikt voor de frontend. |

**Let op:**

- Zet min en max replicas op 1. Anders schaalt de app naar 0 en raakt hij zijn state in het geheugen kwijt.
- De ingress kan lange SSE-verbindingen na een paar minuten verbreken. De browser maakt dan vanzelf opnieuw verbinding. De backend stuurt daarna eerst de huidige state opnieuw.

Taakverdeling: A doet data, stats en MCP. B doet de agents. C doet de frontend en de video.

## Scope

**Nu (MVP):** alles hierboven, behalve de Personalizer en de fanmodus. Daarbij hoort ook een deploy op Container Apps, een README met dit diagram, een demovideo van minder dan 2 minuten en een pitch.

**Als er tijd is (go/no-go op 22 oktober):**

- Personalizer-agent en fanmodus
- Meertalige output in de UI
- Een wedstrijdrecap als apart scherm

**Groeipad (niet bouwen, wel noemen in de pitch):**

- EventBus vervangen door Azure Event Hubs of Service Bus. De interface blijft hetzelfde.
- Agents als losse workers die apart schalen.
- Auto-eventing uit een videofeed (Azure AI Vision of een eigen model).
- Overlay-integratie bij een broadcast-partner via de Overlay JSON.
- Fabric / Real-Time Intelligence voor analyse over meerdere wedstrijden.

## Bronnen

- `claude/architectuur.md` en `claude/synthetische-wedstrijd.md` in het project "Microsoft Premier League"
- [Interactief architectuurdiagram](https://claude.ai/artifact/24Kob5rnzvBf3icoHRti2n)
