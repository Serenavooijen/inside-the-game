# Prompt voor Claude Code: frontend Inside the Game

Bouw de frontend van **Inside the Game**, een live "second screen" voor voetbal, in **Next.js (App Router) + TypeScript + Tailwind CSS**. De UI is in het **Engels**. Eén persoon moet dit in vier dagen kunnen bouwen, dus houd het simpel: geen state-library, geen animatielibrary, geen component-library.

## Ontwerpbestanden

In `design/` staan HTML-prototypes. Dat zijn **ontwerpreferenties, geen productiecode**. Open ze in een browser en bouw ze pixel-precies na in React-componenten met Tailwind.

- `Inside the Game.dc.html`: het overzicht met alle schermen, onderdelen en tokens
- `MatchScreen.dc.html`: het hoofdscherm (veld, overlays, feed, vier toestanden)
- `Scorebar.dc.html`, `Controls.dc.html`, `InsightCard.dc.html`: losse onderdelen

Alle maten, kleuren, posities en teksten staan inline in die bestanden. Kijk daar als iets in deze prompt niet duidelijk is. In de bestanden staan veldposities in **meters** (x 0–105, y 0–68). Die rekenen ze om naar procenten met `left = (x+3)/111`, `top = (y+3)/74`, omdat de SVG-viewBox `-3 -3 111 74` is (3 m marge voor de doelen).

## Stap 1: tokens en Tailwind

1. Zet de CSS-variabelen uit sectie 4 van het overzicht in `app/globals.css`: `:root, .theme-night { … }` en `.theme-day { … }`. Alle namen beginnen met `--itg-`.
2. Neem de `tailwind.config` uit hetzelfde blok over (kleuren via `var(--itg-*)`, fontFamily, fontSize, spacing, radius, easing `out`).
3. Fonts via `next/font/google`: **Barlow Condensed** (600/700/800, `font-display`), **Instrument Serif** (400, `font-serif`), **Geist** (`font-sans`), **JetBrains Mono** (`font-mono`). Zet `font-variant-numeric: tabular-nums` op body.
4. Een theme-toggle zet `theme-night` of `theme-day` op `<html>`. Night is de standaard.

Kleurregels:
- Lime `#D4FF3F` betekent alleen **"AI-duiding"**: het eyebrow-label "AI analysis", de typing-caret, de pulse bij "Analysing…" en de zone op het mini-veld. Op de overlays op het veld komt geen lime.
- Statuskleuren: checked `--itg-ok`, overturned `--itg-bad`, fallback `--itg-fallback` (de fallback heeft een gestippelde rand).
- Kingsbridge (KBA) is blauw `#2F6BFF`, keeper roze `#F06EB4`. Northgate (NGR) is amber `#FFB400` met een zwarte ring, keeper `#202020`. Kaartgeel is `#FFD21F`, rood `#E5383B`.
- Radius: 6 / 10 / 16 / 9999. Gebruik nooit 4px.

## Stap 2: routes

- `/` toont **Pick a match** (startscherm, sectie 2 in het overzicht). Het is een lijst van wedstrijden met twee clubs (crest-fiche + naam), een grote eindstand, een verloop in Instrument Serif 28px, een meta-regel in mono en een knop **Watch**. Alleen de eerste wedstrijd heeft een lime knop, de rest heeft een ghost-knop.
- `/match/[id]` toont het hoofdscherm.
- `/match/[id]?replay=1` toont dezelfde wedstrijd in replay-modus (scorebalk-label "Recorded replay · No live AI", geen live AI-calls, alle tijdlijnmarkers zichtbaar).

## Stap 3: componenten

Maak deze componenten in `components/`. De props zijn een voorstel, pas ze aan de data aan.

**`Scorebar`**, 104px hoog, grid `1fr auto 1fr`.
- Links staan het logo en "Inside the Game", met een Live-pil (pulserende rode stip) of de replay-pil.
- In het midden staat het tv-blok van 60px hoog: KBA-crest + afkorting met een 5px onderrand in teamkleur, de score op een lichte achtergrond (Barlow 800 46px), NGR met crest, en de klok in mono 24px met de periode eronder.
- Onder het blok staat een regel met events (goal, geel, wissel).
- Rechts staan balbezit en xG als getal plus een balk in teamkleuren.

**`Pitch`**, een SVG met viewBox `-3 -3 111 74`, op het scherm 1248×832.
- Gras met 14 maaistroken (`grass-a` en `grass-b` om en om, elk 7,93 m breed) en krijtlijnen op schaal: strafschopgebied 16,5 × 40,32, doelgebied 5,5 × 18,32, middencirkel r 9,15, penaltystippen, bogen, cornerbogen r 1.
- Doelen van 2 m diep met een net-pattern.
- Een radial gradient als lamplicht: midden licht, randen donker.
- Spelers zijn een HTML-laag eroverheen, `absolute` met de procent-formule. Een fiche is 38px met 2px ring, Barlow 800 20px en een schaduw. De bal is een SVG-icoon van 18px.

**`OverlayLayer`** heeft elke overlay een `slot`: `tag | pass | shot | sprint`.
- `tag`: een naamlabel van 34px, rugnummer in teamkleur plus naam in caps op `rgba(12,14,13,.9)`. Het staat naast of boven de speler en mag nooit over een andere chip vallen.
- `pass`: een gestippelde witte lijn met een pijl en een badge "PASS QUALITY" met balk + getal.
- `shot`: een gestippelde lijn naar het doel en een badge "SHOT 96 km/h".
- `sprint`: een spoor in teamkleur (gradient van transparant naar team) achter de loper en een badge "SPRINT · 3 32.1 km/h".
- Overlays verschijnen direct (fade + 4px translate, 200ms, `ease-out`) en verdwijnen na ~4 s. Per slot is er maximaal één tegelijk.

**`InsightCard`** heeft de props `type` (`goal|bigchance|card|momentum|update|fulltime`), `minute`, `team?`, `text`, `status` (`checked|overturned|fallback`), `phase` (`analysing|streaming|done`), `evidence: string[]`, `zone?` (`left|behind`), `size` (`feed|hero`), `mode` (`casual|analyst`), `analystStats?` en voor overturned ook `claim`, `statA/B`, `statA/BLabel` en `statA/BTeam`.
- Opbouw: een kop met icoon, type in Barlow caps, teamstip + afkorting en de minuut rechts groot. Daaronder het eyebrow "AI analysis" (bij fallback "Template text"), dan de tekst in **Instrument Serif** (25px in de feed, 38px als hero). Onderaan de statuspil en de knop "Evidence · n" die het evidence-deel uitklapt (mono 14px, rijen met een hairline ertussen).
- `analysing`: "Analysing…" met een pulserende lime stip en twee skeleton-regels.
- `streaming`: de tekst komt woord voor woord binnen met een knipperende lime caret. Er is nog geen footer.
- `done`: de footer met de status verschijnt.
- `overturned`: een rode balk "VAR · Overturned" met "Checked against event data", de claim doorgestreept, de correctietekst, en twee grote cijfers (Barlow 64px, in teamkleur) met "vs" ertussen. De kaart krijgt een rode rand.
- `fallback`: een gestippelde rand, een pil "Fallback" en een reden in mono ("Model timed out after 6 s").
- Mini-veld (150px in de feed, 220px als hero): alleen als `zone` gezet is en de kaart is uitgeklapt of hero is. Het lime vlak markeert de zone.
- `mode="analyst"`: dezelfde tekst, met daaronder een strip van 3 stats (getal in Barlow 26px, label in mono 11px).

**`ProducerFeed`** is de kolom rechts. Kop "Producer feed" met "NEWEST FIRST" eronder, rechts een segmented control **Casual fan / Analyst**. Kaarten staan in een kolom met 12px tussenruimte, onderaan vervaagt de lijst naar de achtergrond. De nieuwste kaart staat uitgeklapt, de oudere zijn ingeklapt.

**`KeyMoment`** is de tv-regielaag over het veld.
- Het veld wordt 24% donkerder.
- Bovenaan in het midden staat een balk van 64px: `GOAL` (licht), `Kingsbridge 2-1` (teamkleur + crest) en `67'` (donker). Daaronder een regel met wie scoorde en wie de assist gaf.
- Linksboven staat de pil "Key moment · slowed to 1×", rechtsboven "REPLAY".
- Linksonder staat een `InsightCard size="hero"` van 700px breed. Die doorloopt analysing (~2 s), streaming en done.
- Na 6–8 s krimpt en schuift de hero-kaart naar de top van de feed (translate + fade, 480ms, `cubic-bezier(0.22,1,0.36,1)`). Daarna gaat het tempo terug naar 10×.

**`Controls`** zijn 112px hoog.
- Een ronde play/pause-knop van 56px.
- Een tempo-segment `1× / 10×`. Bij een key moment staat ernaast "Auto-slowed for key moment".
- De tijdlijn 0–90 met ticks op 15', 30', HT, 60', 75' en 90'. Het gespeelde deel is wit gevuld, met een knop van 18px.
- Markers boven de balk: goal (cirkel in teamkleur met witte rand), kaart (gele rechthoek), afgewezen claim (rode ruit). Een klik op een marker springt naar die minuut.
- Live toont alleen markers in het verleden, replay toont alle markers.
- Rechts staat de minuut groot, "/ 90'" eronder of ernaast, en "FT" na het eindsignaal.

**Meldingen**
- **Reconnecting**: een pil onderaan in het midden van het veld, met spinner, "Stream dropped. Reconnecting…" en "Retry in 3 s" in mono.
- **VAR**: een pil rechtsboven op het veld met "VAR check · 1 claim overturned", rode rand en een pijl. Een klik scrolt de feed naar die kaart.

## Stap 4: layout van het hoofdscherm

Het scherm is 1920×1080 en `flex-col`: Scorebar (104px), daarna de main met `flex-1`, 16px/40px padding en 32px tussen veld en feed, daarna Controls (112px). Het veld staat vast op 1248×832 en de feed vult de rest.

Op **1440 breed** schaalt het veld met `aspect-ratio: 111/74` en `width: min(1248px, 100% - 440px)`. De feed is dan minimaal 400px breed. Mobiel is niet nodig.

## Stap 5: data en tijd

**De backend is de baas over de tijd.** De wedstrijd wordt afgespeeld door de backend (FastAPI, gebouwd door Bryan). Die stuurt alles via één SSE-stream. Play, pause, tempo en seek zijn HTTP-calls naar die backend. De frontend houdt geen eigen wedstrijdklok bij. Hij volgt de `tick`-berichten en gebruikt `requestAnimationFrame` alleen om tussen twee frames vloeiend te interpoleren.

**Eén databron, twee implementaties.** Alle data komt binnen via één hook, `useMatchStream(matchId)`. Die geeft terug: `frame`, `minute`, `speed`, `playing`, `overlays`, `insights`, `events`, `connection` (`live|reconnecting`), en de acties `play()`, `pause()`, `setSpeed(s)` en `seek(minute)`.

- De bron is één env var, `NEXT_PUBLIC_API_URL`.
- **Mock (nu):** bouw een Next.js-route `app/api/mock/...` die het gedrag van de backend nadoet. `GET /api/mock/stream` speelt `data/matches/kba-ngr.json` af als **echte SSE**, en `POST /api/mock/play|pause|speed|seek` stuurt dat afspelen aan. Zet `NEXT_PUBLIC_API_URL=/api/mock`.
- **Echt (later):** `NEXT_PUBLIC_API_URL=http://localhost:8000`, en later de URL op Azure. Aan de frontend verandert dan niets.

**Endpoints (zelfde vorm bij mock en backend):** `GET /matches`, `POST /match/load {match_id}`, `POST /play`, `POST /pause`, `POST /speed {factor}`, `POST /seek {minute}`, `GET /state`, `GET /stream`.

**SSE-berichten:** `event: <type>` + `data: <json>`, met deze typen:

- `tick`: een `Frame` plus `minute`, `speed`, `playing` en `generation`;
- `overlay`: een `Overlay`;
- `event`: een `MatchEvent`;
- `insight`: een `Insight`. Hetzelfde `id` kan meerdere keren komen: eerst `phase: 'analysing'`, dan `'streaming'` met een groeiende `text`, en daarna `'done'` met de status;
- `state`: de volledige toestand, gestuurd na een (re)connect.

**Regels:**

- Na een seek stuurt de backend een nieuw `generation`-nummer. De frontend gooit overlays en inzichten met een oud `generation` weg.
- Na een reconnect roept de frontend `GET /state` aan en bouwt het beeld daaruit opnieuw op. `EventSource` maakt zelf opnieuw verbinding; toon dan de melding "Reconnecting".
- De types hieronder zijn het voorstel voor het contract met de backend. Zet ze in `lib/contracts.ts` en wijk er niet zomaar van af: Bryan gebruikt dezelfde velden in Pydantic.

Het fixture-bestand `data/matches/kba-ngr.json` gebruikt deze types:

```ts
type Frame = { t: number; players: { id: string; team: 'kba'|'ngr'; n: number; x: number; y: number; gk?: boolean; name?: string }[]; ball: { x: number; y: number } };
type Overlay = { t: number; slot: 'tag'|'pass'|'shot'|'sprint'; playerId: string; value?: number; to?: { x: number; y: number } };
type MatchEvent = { t: number; kind: 'goal'|'yellow'|'red'|'sub'|'bigchance'; team: 'kba'|'ngr'; text: string; key?: boolean };
type Insight = { id: string; t: number; type: InsightCardProps['type']; team?: 'kba'|'ngr'; text: string; status: 'checked'|'overturned'|'fallback'; evidence: string[]; zone?: 'left'|'behind'; claim?: string; stats?: { a: string; aLabel: string; aTeam: string; b: string; bLabel: string; bTeam: string }; analystStats?: { k: string; v: string }[] };
```

Voeg aan `Overlay` en `Insight` ook `generation: number` toe, en aan `Insight` het veld `phase: 'analysing'|'streaming'|'done'`.

- Interpoleer spelers lineair tussen frames. De generator maakt 1 frame per wedstrijdseconde.
- Een event met `key: true` start `KeyMoment`. Het vertragen naar 1× gebeurt in de backend; de frontend toont het via `speed` in de `tick`. De mock doet hetzelfde.
- De fallback-tekst komt ook van de backend (`status: 'fallback'`). De frontend kiest hem niet zelf.
- In replay-modus (`?replay=1`) komt alles uit een opgenomen run. Er zijn dan geen live AI-calls.
- Maak in de fixture minstens: 10 minuten frames rond de 67e minuut, de goal van 67' met een inzicht dat de drie fases doorloopt, één inzicht met `status: 'fallback'` en één met `status: 'overturned'` rond 86'.

## Inhoud

Gebruik de teksten, namen en cijfers uit de prototypes letterlijk: Kingsbridge Athletic – Northgate Rovers, 2-2, xG 2.48 – 1.52, balbezit 58–42, field tilt 79%, PPDA 5.1 – 11.1. Neem ook de drie voorbeeldinzichten over en de overturned-claim "Northgate did not create more chances after half-time, 3 shots vs 7." Alles is fictief. Gebruik geen echte merken, logo's of lettertypes van de Premier League, Microsoft, clubs of zenders.

## Toegankelijkheid en motion

- Contrast minimaal 4.5:1. In het lichte thema hebben de teamteksten donkerdere varianten (`kba-text`, `ngr-text`, `accent-text`).
- Alle knoppen zijn bedienbaar met het toetsenbord en krijgen een focus ring van 2px lime met 2px offset.
- Bij `prefers-reduced-motion` gaan de caret en pulse uit, komt de tekst direct in beeld en worden overgangen alleen fades.

## Volgorde (vier dagen)

1. **Dag 1:** tokens, fonts, `Pitch`, spelers en bal, `lib/contracts.ts`, de mock-SSE-route, `useMatchStream` en `Controls`.
2. **Dag 2:** `Scorebar` en `OverlayLayer`, en de echte backend aansluiten als die er al is.
3. **Dag 3:** `InsightCard` in alle toestanden, `ProducerFeed` en `KeyMoment` met de overgang naar de feed.
4. **Dag 4:** startscherm, replay, reconnecting, licht thema, check op 1440 breed en de demo-run (key moment op 67', overturned op 86').

Klaar is als de demo zonder uitleg te volgen is: Live op 10×, een goal met auto-slow en een kaart die de drie fases doorloopt, en één afgewezen claim die zichtbaar wordt.
