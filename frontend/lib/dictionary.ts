import type { Translation } from './contracts';

/**
 * Languages for this viewer. The agents write and check in English; the backend's Translator sends a checked
 * translation per card afterwards (`translations`). Fixed UI texts come from the small dictionary below.
 * The choice is per viewer and stays in localStorage. No right-to-left languages: they need layout work first.
 */
export type Lang = 'en' | 'nl' | 'es' | 'fr';

export const LANGS: { code: Lang; name: string }[] = [
  { code: 'en', name: 'English' }, { code: 'nl', name: 'Nederlands' }, { code: 'es', name: 'Español' }, { code: 'fr', name: 'Français' },
];

export const STORAGE_KEY = 'itg-lang';

const en = {
  // header ("Live" is the broadcast term in every language, and the longer words do not fit at 1440 px)
  live: 'Live', replay: 'Recorded replay', noLiveAi: 'No live AI', possession: 'Possession', language: 'Language',
  dayTheme: 'Day theme', nightTheme: 'Night theme',
  p1: '1st half', p2: '2nd half', p3: 'Extra time 1', p4: 'Extra time 2', p5: 'Penalties', fullTime: 'Full time',
  // pitch and commentary
  commentary: 'Commentary', factCheckPill: 'Fact-check · 1 claim corrected', reconnecting: 'Stream dropped. Reconnecting…',
  retryIn: 'Retry in 3 s', loading: 'Loading match…',
  keyMoment: 'Key moment · slowed to 1×', replayTag: 'Replay',
  barGoal: 'Goal', barBigchance: 'Big chance', barCard: 'Card', barRed: 'Red card', barSub: 'Sub',
  // feed
  casual: 'Casual fan', analyst: 'Analyst', explanationStyle: 'Explanation style',
  tabFeed: 'Feed', tabScouting: 'Scouting report (cup)', tabLineups: 'Line-ups', scoutingCard: 'Scouting report (cup)',
  producerFeed: 'Producer feed', newestFirst: 'Newest first', scouting: 'Scouting', cupBeforeKickoff: 'The cup match, before kick-off',
  lineups: 'Line-ups', vs: 'vs', emptyFeed: 'Insights appear here at key moments and every five minutes.',
  // cards
  goal: 'Goal', bigchance: 'Big chance', card: 'Card', redCard: 'Red card', momentum: 'Momentum', update: '5-min update',
  fulltime: 'Full time', tactics: 'Tactics', substitution: 'Substitution',
  templateText: 'Template text', aiAnalysis: 'AI analysis', analysing: 'Analysing…', corrected: 'Corrected', checked: 'Checked',
  fallback: 'Fallback', checkedAgainst: 'Checked against event data', removed: 'Removed', notBacked: 'Not backed by the event data',
  modelTimedOut: 'Model timed out · template used', evidence: 'Evidence', evidenceSource: 'Source data · EN',
  translatedChecked: 'translated · checked', original: 'original · EN', showOriginal: 'Show the English original',
  showTranslation: 'Show the translation', englishOnly: 'English text: no checked translation',
  translating: 'English text: translation on its way',
  // tactics and substitutions
  every5: 'Every 5 minutes', halfTime: 'Half time', afterSub: 'After the substitution', cupMatch: 'Cup match',
  noChange: 'No tactical change', asInCup: 'As in the cup', changedSinceCup: 'Changed since the cup',
  presence: 'Presence', buildUp: 'mean build-up positions', consequence: 'Consequence', forCoach: 'For the coach',
  leftOut: 'Not verifiable · left out', scoutUnavailable: 'Scout unavailable · facts and playbook used',
  ko: 'KO', factsPlaybook: 'Facts + playbook', measuredByCode: 'Measured by the code', scoutAi: 'Scout · AI analysis',
  readingShape: 'Reading the shape…', scoutingReport: 'Scouting report', madeBeforeKickoff: 'Made before kick-off · baseline for every tactics card',
  by: 'by {x}', likeForLike: 'Like for like', positional: 'Positional', shapeChange: 'Shape change',
  impactSince: "Impact · Scout · since {m}'", whatToWatch: 'What to watch · measured by the code', readingChange: 'Reading the change…',
  replacedBy: 'replaced by',
  // controls
  play: 'Play', pause: 'Pause', speed: 'Playback speed', autoSlowed: 'Auto-slowed for key moment', ht: 'HT', ft: 'FT',
  matchTime: 'Match time', jumpTo: "jump to {m}'",
  // line-ups
  attacking: 'Attacking', onTheBench: 'On the bench', formation: 'Formation', averagePositions: 'Average positions',
  pitchView: 'Pitch view', team: 'Team', shapeAt: "Shape at {m}' · players on the pitch now",
  avgNote: "Average positions · 0–{m}'", dimmedSentOff: 'dimmed = sent off', lineHeight: 'Average line height: {h} m from own goal',
  startingXI: 'Starting XI', substitutes: 'Substitutes', openPlayer: 'open player analysis',
  // player analysis
  back: 'Back', notOnPitch: 'Not on the pitch', shownOnPitch: 'Shown on pitch', showOnPitch: 'Show on pitch',
  onThePitch: 'On the pitch', subbedOff: "Subbed off {m}'", sentOff: "Sent off {m}'", benchNotPlayed: 'On the bench · not played yet',
  final: 'Final', played: 'played', keyNumbers: 'Key numbers', liveEvery10: 'Live · updates every 10 s',
  startsWhenOn: 'Starts when he comes on', frozenAt: "Frozen at {m}'", heatmap: 'Heatmap', noData: 'no data',
  wholeMatch: 'Whole match', last15: 'Last 15 min', heatmapEmpty: 'No data yet. The heatmap starts when he comes on.',
  bothHalves: 'Both halves shown left to right', averagePosition: 'Average position', less: 'Less', more: 'More',
  moments: 'Moments', noMinutes: 'No minutes yet', replacedByAt: "Replaced by · {m}'", replacedAt: "Replaced · {m}'",
  noReplacement: "No replacement. {team} played with 10 men from {m}'.",
  touches: 'Touches', passes: 'Passes', shots: 'Shots', sprints: 'Sprints', distance: 'Distance', topSpeed: 'Top speed',
  duelsWon: 'Duels won', recoveries: 'Recoveries', minutes: 'Minutes', goals: 'Goals',
  tileTouches: 'Touches', tileTopSpeed: 'Top speed', tileDuelsWon: 'Duels won', tileRecoveries: 'Recoveries',
  mGoal: 'Goal', mAssist: 'Assist', mYellow: 'Yellow', mRed: 'Red', mOff: 'Off', mOn: 'On',
  // corners
  corner: 'Corner', cornerFor: '{nth} corner for {team}', fromLeft: 'From the left', fromRight: 'From the right',
  eventData: 'Event data', nearPost: 'Near post', farPost: 'Far post', penaltySpot: 'Penalty spot', edgeOfBox: 'Edge of the box',
  short: 'Short', corners: 'Corners', left: 'Left', right: 'Right', deliveryZone: 'Delivery zone', mainTarget: 'Main target',
  firstContacts: '{h} of {n} first contacts', noFirstContact: 'No first contact won yet', noCorners: 'No corners yet',
  goalsFromCorners: 'Goals from corners', thisMatch: 'This match', cupShort: 'Cup match',
  oHeader: 'Header by {x}', oShot: 'Shot by {x}', oGoal: 'Goal', oCleared: 'Cleared by {x}', oPlayedOut: 'Played out',
  oTo: 'to {x}', oEdge: 'Played to the edge of the box', oShortTo: 'Short corner · played to {x}', oOffTarget: 'off target',
  oOnTarget: 'on target', oSaved: 'saved', oBlocked: 'blocked', oNotReached: 'Not reached · out of play', oNoShot: 'no shot',
  oFirstContact: 'First contact {x}',
  // your view (favourite club and player)
  yourView: 'Your view',
  savedOnDevice: 'Saved on this device',
  profile: 'Your view: club, player, language',
  club: 'Club',
  player: 'Player',
  viewLabel: 'View',
  neutral: 'Neutral',
  change: 'Change',
  stopFollowing: 'Stop following',
  noPlayer: 'No player followed',
  choosePlayer: 'Choose a player',
  resetNeutral: 'Reset to Neutral',
  followPlayer: 'Follow player',
  following: 'Following',
  yourClub: 'Your club',
  filterAll: 'All',
  filterClub: 'My club',
  filterPlayer: 'My player',
  feedFilter: 'Show cards',
  stripOnPitch: 'On pitch',
  cameOn: '{name} came on',
  followName: 'Follow {name}',
  stripBench: 'On the bench. His numbers start when he comes on.',
  nowPlaying: 'Now {f}',
  showMore: 'Show more',
  showLess: 'Show less',
  km: 'Km',
  close: 'Close',
  // tactics per club
  clubView: '{club} view',
  howToBeat: 'How to beat {team}',
  changedToday: 'What {team} changed today',
  changedLabel: 'Changed',
  sameLabel: 'Same',
  tacticsView: 'Tactics view',
  lever: 'Lever {n}',
};

export type Key = keyof typeof en;
type Dict = Record<Key, string>;

const nl: Dict = {
  live: 'Live', replay: 'Opgenomen herhaling', noLiveAi: 'Geen live AI', possession: 'Balbezit', language: 'Taal',
  dayTheme: 'Dagthema', nightTheme: 'Nachtthema',
  p1: '1e helft', p2: '2e helft', p3: 'Verlenging 1', p4: 'Verlenging 2', p5: 'Strafschoppen', fullTime: 'Einde wedstrijd',
  commentary: 'Commentaar', factCheckPill: 'Factcheck · 1 bewering gecorrigeerd', reconnecting: 'Verbinding verbroken. Opnieuw verbinden…',
  retryIn: 'Nieuwe poging over 3 s', loading: 'Wedstrijd laden…',
  keyMoment: 'Sleutelmoment · vertraagd naar 1×', replayTag: 'Herhaling',
  barGoal: 'Goal', barBigchance: 'Grote kans', barCard: 'Kaart', barRed: 'Rode kaart', barSub: 'Wissel',
  casual: 'Fan', analyst: 'Analist', explanationStyle: 'Uitlegstijl',
  tabFeed: 'Feed', tabScouting: 'Scoutingrapport (beker)', tabLineups: 'Opstellingen', scoutingCard: 'Scouting (beker)',
  producerFeed: 'Producer-feed', newestFirst: 'Nieuwste eerst', scouting: 'Scouting', cupBeforeKickoff: 'De bekerwedstrijd, voor de aftrap',
  lineups: 'Opstellingen', vs: 'tegen', emptyFeed: 'Analyses verschijnen hier bij belangrijke momenten en elke vijf minuten.',
  goal: 'Goal', bigchance: 'Grote kans', card: 'Kaart', redCard: 'Rode kaart', momentum: 'Momentum', update: '5-min-update',
  fulltime: 'Einde wedstrijd', tactics: 'Tactiek', substitution: 'Wissel',
  templateText: 'Sjabloontekst', aiAnalysis: 'AI-analyse', analysing: 'Analyseren…', corrected: 'Gecorrigeerd', checked: 'Gecontroleerd',
  fallback: 'Terugval', checkedAgainst: 'Gecontroleerd met eventdata', removed: 'Verwijderd', notBacked: 'Niet onderbouwd door de eventdata',
  modelTimedOut: 'Model te laat · sjabloon gebruikt', evidence: 'Bewijs', evidenceSource: 'Brondata · EN',
  translatedChecked: 'vertaald · gecontroleerd', original: 'origineel · EN', showOriginal: 'Toon het Engelse origineel',
  showTranslation: 'Toon de vertaling', englishOnly: 'Engelse tekst: geen gecontroleerde vertaling',
  translating: 'Engelse tekst: vertaling onderweg',
  every5: 'Elke 5 minuten', halfTime: 'Rust', afterSub: 'Na de wissel', cupMatch: 'Bekerwedstrijd',
  noChange: 'Geen tactische verandering', asInCup: 'Zoals in de beker', changedSinceCup: 'Anders dan in de beker',
  presence: 'Aanwezigheid', buildUp: 'gemiddelde posities in de opbouw', consequence: 'Gevolg', forCoach: 'Voor de trainer',
  leftOut: 'Niet controleerbaar · weggelaten', scoutUnavailable: 'Scout niet beschikbaar · feiten en playbook gebruikt',
  ko: 'Vooraf', factsPlaybook: 'Feiten + playbook', measuredByCode: 'Gemeten door de code', scoutAi: 'Scout · AI-analyse',
  readingShape: 'De vorm lezen…', scoutingReport: 'Scoutingrapport', madeBeforeKickoff: 'Gemaakt voor de aftrap · basis voor elke tactiekkaart',
  by: 'door {x}', likeForLike: 'Een-op-een', positional: 'Positioneel', shapeChange: 'Andere vorm',
  impactSince: "Effect · Scout · sinds {m}'", whatToWatch: 'Om op te letten · gemeten door de code', readingChange: 'De wissel lezen…',
  replacedBy: 'vervangen door',
  play: 'Afspelen', pause: 'Pauzeren', speed: 'Afspeelsnelheid', autoSlowed: 'Vertraagd voor sleutelmoment', ht: 'Rust', ft: 'Eind',
  matchTime: 'Wedstrijdtijd', jumpTo: "naar {m}'",
  attacking: 'Aanvalsrichting', onTheBench: 'Op de bank', formation: 'Formatie', averagePositions: 'Gemiddelde posities',
  pitchView: 'Veldweergave', team: 'Team', shapeAt: "Vorm op {m}' · spelers nu op het veld",
  avgNote: "Gemiddelde posities · 0–{m}'", dimmedSentOff: 'gedimd = weggestuurd', lineHeight: 'Gemiddelde linie: {h} m van eigen doel',
  startingXI: 'Basiself', substitutes: 'Wisselspelers', openPlayer: 'open spelersanalyse',
  back: 'Terug', notOnPitch: 'Niet op het veld', shownOnPitch: 'Getoond op het veld', showOnPitch: 'Toon op het veld',
  onThePitch: 'Op het veld', subbedOff: "Gewisseld {m}'", sentOff: "Weggestuurd {m}'", benchNotPlayed: 'Op de bank · nog niet gespeeld',
  final: 'Eindstand', played: 'gespeeld', keyNumbers: 'Kerncijfers', liveEvery10: 'Live · elke 10 s bijgewerkt',
  startsWhenOn: 'Begint als hij invalt', frozenAt: "Bevroren op {m}'", heatmap: 'Heatmap', noData: 'geen data',
  wholeMatch: 'Hele wedstrijd', last15: 'Laatste 15 min', heatmapEmpty: 'Nog geen data. De heatmap begint als hij invalt.',
  bothHalves: 'Beide helften van links naar rechts', averagePosition: 'Gemiddelde positie', less: 'Minder', more: 'Meer',
  moments: 'Momenten', noMinutes: 'Nog geen minuten', replacedByAt: "Vervangen door · {m}'", replacedAt: "Verving · {m}'",
  noReplacement: "Geen vervanger. {team} speelde vanaf {m}' met 10 man.",
  touches: 'Balcontacten', passes: 'Passes', shots: 'Schoten', sprints: 'Sprints', distance: 'Afstand', topSpeed: 'Topsnelheid',
  duelsWon: 'Duels gewonnen', recoveries: 'Balveroveringen', minutes: 'Minuten', goals: 'Goals',
  tileTouches: 'Balcontact', tileTopSpeed: 'Topsnelheid', tileDuelsWon: 'Duels gew.', tileRecoveries: 'Veroverd',
  mGoal: 'Goal', mAssist: 'Assist', mYellow: 'Geel', mRed: 'Rood', mOff: 'Eruit', mOn: 'Erin',
  corner: 'Corner', cornerFor: '{nth} corner voor {team}', fromLeft: 'Van links', fromRight: 'Van rechts',
  eventData: 'Eventdata', nearPost: 'Eerste paal', farPost: 'Tweede paal', penaltySpot: 'Penaltystip', edgeOfBox: 'Rand van de zestien',
  short: 'Kort', corners: 'Corners', left: 'Links', right: 'Rechts', deliveryZone: 'Zone van de voorzet', mainTarget: 'Belangrijkste doelwit',
  firstContacts: '{h}/{n} eerste contacten', noFirstContact: 'Nog geen eerste contact gewonnen', noCorners: 'Nog geen corners',
  goalsFromCorners: 'Goals uit corners', thisMatch: 'Vandaag', cupShort: 'Beker',
  oHeader: 'Kopbal van {x}', oShot: 'Schot van {x}', oGoal: 'Goal', oCleared: 'Weggewerkt door {x}', oPlayedOut: 'Uitgespeeld',
  oTo: 'naar {x}', oEdge: 'Gespeeld naar de rand van de zestien', oShortTo: 'Korte corner · gespeeld naar {x}', oOffTarget: 'naast',
  oOnTarget: 'op doel', oSaved: 'gekeerd', oBlocked: 'geblokt', oNotReached: 'Niemand bij · over de lijn', oNoShot: 'geen schot',
  oFirstContact: 'Eerste contact {x}',
  // your view (favourite club and player)
  yourView: 'Jouw weergave',
  savedOnDevice: 'Bewaard op dit apparaat',
  profile: 'Jouw weergave: club, speler, taal',
  club: 'Club',
  player: 'Speler',
  viewLabel: 'Weergave',
  neutral: 'Neutraal',
  change: 'Wijzig',
  stopFollowing: 'Stop met volgen',
  noPlayer: 'Geen speler gevolgd',
  choosePlayer: 'Kies een speler',
  resetNeutral: 'Terug naar neutraal',
  followPlayer: 'Volg speler',
  following: 'Gevolgd',
  yourClub: 'Jouw club',
  filterAll: 'Alles',
  filterClub: 'Mijn club',
  filterPlayer: 'Mijn speler',
  feedFilter: 'Toon kaarten',
  stripOnPitch: 'Op het veld',
  cameOn: '{name} kwam erin',
  followName: 'Volg {name}',
  stripBench: 'Op de bank. Zijn cijfers beginnen als hij invalt.',
  nowPlaying: 'Nu {f}',
  showMore: 'Meer tonen',
  showLess: 'Minder tonen',
  km: 'Km',
  close: 'Sluiten',
  // tactics per club
  clubView: '{club}-weergave',
  howToBeat: 'Zo versla je {team}',
  changedToday: 'Wat {team} vandaag anders doet',
  changedLabel: 'Anders',
  sameLabel: 'Gelijk',
  tacticsView: 'Tactiekweergave',
  lever: 'Hefboom {n}',
};

const es: Dict = {
  live: 'Live', replay: 'Repetición grabada', noLiveAi: 'Sin IA en directo', possession: 'Posesión', language: 'Idioma',
  dayTheme: 'Tema de día', nightTheme: 'Tema de noche',
  p1: '1.ª parte', p2: '2.ª parte', p3: 'Prórroga 1', p4: 'Prórroga 2', p5: 'Penaltis', fullTime: 'Final',
  commentary: 'Comentario', factCheckPill: 'Verificación · 1 afirmación corregida', reconnecting: 'Se cortó la señal. Reconectando…',
  retryIn: 'Reintento en 3 s', loading: 'Cargando partido…',
  keyMoment: 'Momento clave · a velocidad 1×', replayTag: 'Repetición',
  barGoal: 'Gol', barBigchance: 'Ocasión clara', barCard: 'Tarjeta', barRed: 'Tarjeta roja', barSub: 'Cambio',
  casual: 'Aficionado', analyst: 'Analista', explanationStyle: 'Estilo de explicación',
  tabFeed: 'Directo', tabScouting: 'Informe de scouting (copa)', tabLineups: 'Alineaciones', scoutingCard: 'Scouting (copa)',
  producerFeed: 'Feed de realización', newestFirst: 'Lo más reciente primero', scouting: 'Scouting', cupBeforeKickoff: 'Partido de copa · previa',
  lineups: 'Alineaciones', vs: 'contra', emptyFeed: 'Los análisis aparecen aquí en los momentos clave y cada cinco minutos.',
  goal: 'Gol', bigchance: 'Ocasión clara', card: 'Tarjeta', redCard: 'Tarjeta roja', momentum: 'Dinámica', update: 'Resumen 5 min',
  fulltime: 'Final', tactics: 'Táctica', substitution: 'Cambio',
  templateText: 'Texto de plantilla', aiAnalysis: 'Análisis IA', analysing: 'Analizando…', corrected: 'Corregido', checked: 'Verificado',
  fallback: 'Alternativa', checkedAgainst: 'Verificado con los datos de eventos', removed: 'Eliminado', notBacked: 'Sin respaldo en los datos de eventos',
  modelTimedOut: 'El modelo tardó demasiado · se usó la plantilla', evidence: 'Pruebas', evidenceSource: 'Datos de origen · EN',
  translatedChecked: 'traducido · verificado', original: 'original · EN', showOriginal: 'Ver el original en inglés',
  showTranslation: 'Ver la traducción', englishOnly: 'Texto en inglés: sin traducción verificada',
  translating: 'Texto en inglés: traducción en camino',
  every5: 'Cada 5 minutos', halfTime: 'Descanso', afterSub: 'Tras el cambio', cupMatch: 'Partido de copa',
  noChange: 'Sin cambio táctico', asInCup: 'Como en la copa', changedSinceCup: 'Distinto a la copa',
  presence: 'Presencia', buildUp: 'posiciones medias en la salida', consequence: 'Consecuencia', forCoach: 'Para el entrenador',
  leftOut: 'No verificable · omitido', scoutUnavailable: 'Scout no disponible · hechos y manual usados',
  ko: 'Previa', factsPlaybook: 'Hechos + manual', measuredByCode: 'Medido por el código', scoutAi: 'Scout · análisis IA',
  readingShape: 'Leyendo el dibujo…', scoutingReport: 'Informe de scouting', madeBeforeKickoff: 'Hecho antes del inicio · base de cada tarjeta táctica',
  by: 'por {x}', likeForLike: 'Mismo puesto', positional: 'Posicional', shapeChange: 'Cambio de dibujo',
  impactSince: "Impacto · Scout · desde el {m}'", whatToWatch: 'Qué observar · medido por el código', readingChange: 'Leyendo el cambio…',
  replacedBy: 'sustituido por',
  play: 'Reproducir', pause: 'Pausa', speed: 'Velocidad', autoSlowed: 'Ralentizado por momento clave', ht: 'Desc.', ft: 'Final',
  matchTime: 'Tiempo de partido', jumpTo: "ir al {m}'",
  attacking: 'Ataca', onTheBench: 'En el banquillo', formation: 'Formación', averagePositions: 'Posiciones medias',
  pitchView: 'Vista del campo', team: 'Equipo', shapeAt: "Dibujo en el {m}' · jugadores en el campo ahora",
  avgNote: "Posiciones medias · 0–{m}'", dimmedSentOff: 'atenuado = expulsado', lineHeight: 'Altura media de la línea: {h} m de su portería',
  startingXI: 'Once inicial', substitutes: 'Suplentes', openPlayer: 'abrir análisis del jugador',
  back: 'Volver', notOnPitch: 'No está en el campo', shownOnPitch: 'Marcado en el campo', showOnPitch: 'Marcar en el campo',
  onThePitch: 'En el campo', subbedOff: "Sustituido {m}'", sentOff: "Expulsado {m}'", benchNotPlayed: 'En el banquillo · aún no ha jugado',
  final: 'Final', played: 'jugados', keyNumbers: 'Cifras clave', liveEvery10: 'En directo · cada 10 s',
  startsWhenOn: 'Empieza cuando entre', frozenAt: "Congelado en el {m}'", heatmap: 'Mapa de calor', noData: 'sin datos',
  wholeMatch: 'Todo el partido', last15: 'Últimos 15 min', heatmapEmpty: 'Aún no hay datos. El mapa de calor empieza cuando entre.',
  bothHalves: 'Ambas partes de izquierda a derecha', averagePosition: 'Posición media', less: 'Menos', more: 'Más',
  moments: 'Momentos', noMinutes: 'Aún sin minutos', replacedByAt: "Sustituido por · {m}'", replacedAt: "Sustituyó a · {m}'",
  noReplacement: "Sin sustituto. {team} jugó con 10 desde el {m}'.",
  touches: 'Toques', passes: 'Pases', shots: 'Tiros', sprints: 'Sprints', distance: 'Distancia', topSpeed: 'Velocidad máx.',
  duelsWon: 'Duelos ganados', recoveries: 'Recuperaciones', minutes: 'Minutos', goals: 'Goles',
  tileTouches: 'Toques', tileTopSpeed: 'Vel. máx.', tileDuelsWon: 'Duelos gan.', tileRecoveries: 'Recup.',
  mGoal: 'Gol', mAssist: 'Asistencia', mYellow: 'Amarilla', mRed: 'Roja', mOff: 'Sale', mOn: 'Entra',
  corner: 'Córner', cornerFor: '{nth} córner de {team}', fromLeft: 'Desde la izquierda', fromRight: 'Desde la derecha',
  eventData: 'Datos de eventos', nearPost: 'Primer palo', farPost: 'Segundo palo', penaltySpot: 'Punto de penalti', edgeOfBox: 'Frontal del área',
  short: 'En corto', corners: 'Córners', left: 'Izq.', right: 'Der.', deliveryZone: 'Zona de envío', mainTarget: 'Objetivo principal',
  firstContacts: '{h}/{n} primeros contactos', noFirstContact: 'Aún sin primer contacto ganado', noCorners: 'Aún sin córners',
  goalsFromCorners: 'Goles de córner', thisMatch: 'Hoy', cupShort: 'Copa',
  oHeader: 'Cabezazo de {x}', oShot: 'Tiro de {x}', oGoal: 'Gol', oCleared: 'Despejado por {x}', oPlayedOut: 'Jugado en corto',
  oTo: 'a {x}', oEdge: 'Jugado a la frontal del área', oShortTo: 'Córner en corto · jugado a {x}', oOffTarget: 'fuera',
  oOnTarget: 'a puerta', oSaved: 'parado', oBlocked: 'bloqueado', oNotReached: 'Nadie llega · fuera', oNoShot: 'sin tiro',
  oFirstContact: 'Primer contacto {x}',
  // your view (favourite club and player)
  yourView: 'Tu vista',
  savedOnDevice: 'Guardado en este dispositivo',
  profile: 'Tu vista: club, jugador, idioma',
  club: 'Club',
  player: 'Jugador',
  viewLabel: 'Vista',
  neutral: 'Neutral',
  change: 'Cambiar',
  stopFollowing: 'Dejar de seguir',
  noPlayer: 'Ningún jugador seguido',
  choosePlayer: 'Elige un jugador',
  resetNeutral: 'Volver a neutral',
  followPlayer: 'Seguir jugador',
  following: 'Siguiendo',
  yourClub: 'Tu club',
  filterAll: 'Todo',
  filterClub: 'Mi club',
  filterPlayer: 'Mi jugador',
  feedFilter: 'Mostrar tarjetas',
  stripOnPitch: 'En el campo',
  cameOn: 'Entró {name}',
  followName: 'Seguir a {name}',
  stripBench: 'En el banquillo. Sus cifras empiezan cuando entre.',
  nowPlaying: 'Ahora {f}',
  showMore: 'Ver más',
  showLess: 'Ver menos',
  km: 'Km',
  close: 'Cerrar',
  // tactics per club
  clubView: 'Vista {club}',
  howToBeat: 'Cómo ganar a {team}',
  changedToday: 'Qué cambió {team} hoy',
  changedLabel: 'Cambió',
  sameLabel: 'Igual',
  tacticsView: 'Vista táctica',
  lever: 'Clave {n}',
};

const fr: Dict = {
  live: 'Live', replay: 'Rediffusion', noLiveAi: 'Pas d’IA en direct', possession: 'Possession', language: 'Langue',
  dayTheme: 'Thème jour', nightTheme: 'Thème nuit',
  p1: '1re mi-temps', p2: '2e mi-temps', p3: 'Prolongation 1', p4: 'Prolongation 2', p5: 'Tirs au but', fullTime: 'Fin du match',
  commentary: 'Commentaire', factCheckPill: 'Vérification · 1 affirmation corrigée', reconnecting: 'Flux coupé. Reconnexion…',
  retryIn: 'Nouvel essai dans 3 s', loading: 'Chargement du match…',
  keyMoment: 'Moment clé · ralenti à 1×', replayTag: 'Ralenti',
  barGoal: 'But', barBigchance: 'Grosse occasion', barCard: 'Carton', barRed: 'Carton rouge', barSub: 'Changement',
  casual: 'Supporter', analyst: 'Analyste', explanationStyle: 'Style d’explication',
  tabFeed: 'Fil', tabScouting: 'Rapport de scouting (coupe)', tabLineups: 'Compositions', scoutingCard: 'Scouting (coupe)',
  producerFeed: 'Fil de réalisation', newestFirst: 'Le plus récent d’abord', scouting: 'Scouting', cupBeforeKickoff: 'Match de coupe · avant-match',
  lineups: 'Compositions', vs: 'contre', emptyFeed: 'Les analyses apparaissent ici aux moments clés et toutes les cinq minutes.',
  goal: 'But', bigchance: 'Grosse occasion', card: 'Carton', redCard: 'Carton rouge', momentum: 'Dynamique', update: 'Point 5 min',
  fulltime: 'Fin du match', tactics: 'Tactique', substitution: 'Changement',
  templateText: 'Texte modèle', aiAnalysis: 'Analyse IA', analysing: 'Analyse…', corrected: 'Corrigé', checked: 'Vérifié',
  fallback: 'Secours', checkedAgainst: 'Vérifié avec les données d’événements', removed: 'Retiré', notBacked: 'Non étayé par les données d’événements',
  modelTimedOut: 'Modèle trop lent · modèle de texte utilisé', evidence: 'Preuves', evidenceSource: 'Données source · EN',
  translatedChecked: 'traduit · vérifié', original: 'original · EN', showOriginal: 'Voir l’original anglais',
  showTranslation: 'Voir la traduction', englishOnly: 'Texte anglais : pas de traduction vérifiée',
  translating: 'Texte anglais : traduction en cours',
  every5: 'Toutes les 5 minutes', halfTime: 'Mi-temps', afterSub: 'Après le changement', cupMatch: 'Match de coupe',
  noChange: 'Pas de changement tactique', asInCup: 'Comme en coupe', changedSinceCup: 'Différent de la coupe',
  presence: 'Présence', buildUp: 'positions moyennes à la relance', consequence: 'Conséquence', forCoach: 'Pour l’entraîneur',
  leftOut: 'Non vérifiable · retiré', scoutUnavailable: 'Scout indisponible · faits et playbook utilisés',
  ko: 'Avant', factsPlaybook: 'Faits + playbook', measuredByCode: 'Mesuré par le code', scoutAi: 'Scout · analyse IA',
  readingShape: 'Lecture du dispositif…', scoutingReport: 'Rapport de scouting', madeBeforeKickoff: 'Fait avant le coup d’envoi · base de chaque carte tactique',
  by: 'par {x}', likeForLike: 'Poste pour poste', positional: 'Positionnel', shapeChange: 'Changement de système',
  impactSince: "Impact · Scout · depuis la {m}'", whatToWatch: 'À surveiller · mesuré par le code', readingChange: 'Lecture du changement…',
  replacedBy: 'remplacé par',
  play: 'Lecture', pause: 'Pause', speed: 'Vitesse', autoSlowed: 'Ralenti pour un moment clé', ht: 'MT', ft: 'Fin',
  matchTime: 'Temps de jeu', jumpTo: "aller à la {m}'",
  attacking: 'Attaque', onTheBench: 'Sur le banc', formation: 'Système', averagePositions: 'Positions moyennes',
  pitchView: 'Vue du terrain', team: 'Équipe', shapeAt: "Dispositif à la {m}' · joueurs sur le terrain",
  avgNote: "Positions moyennes · 0–{m}'", dimmedSentOff: 'estompé = expulsé', lineHeight: 'Hauteur moyenne de la ligne : {h} m de son but',
  startingXI: 'Onze de départ', substitutes: 'Remplaçants', openPlayer: 'ouvrir l’analyse du joueur',
  back: 'Retour', notOnPitch: 'Pas sur le terrain', shownOnPitch: 'Affiché sur le terrain', showOnPitch: 'Afficher sur le terrain',
  onThePitch: 'Sur le terrain', subbedOff: "Remplacé {m}'", sentOff: "Expulsé {m}'", benchNotPlayed: 'Sur le banc · n’a pas encore joué',
  final: 'Final', played: 'joués', keyNumbers: 'Chiffres clés', liveEvery10: 'En direct · toutes les 10 s',
  startsWhenOn: 'Commence à son entrée', frozenAt: "Figé à la {m}'", heatmap: 'Carte de chaleur', noData: 'pas de données',
  wholeMatch: 'Tout le match', last15: '15 dernières min', heatmapEmpty: 'Pas encore de données. La carte commence à son entrée.',
  bothHalves: 'Les deux mi-temps de gauche à droite', averagePosition: 'Position moyenne', less: 'Moins', more: 'Plus',
  moments: 'Moments', noMinutes: 'Pas encore de minutes', replacedByAt: "Remplacé par · {m}'", replacedAt: "A remplacé · {m}'",
  noReplacement: "Pas de remplaçant. {team} a joué à 10 dès la {m}'.",
  touches: 'Ballons touchés', passes: 'Passes', shots: 'Tirs', sprints: 'Sprints', distance: 'Distance', topSpeed: 'Vitesse max.',
  duelsWon: 'Duels gagnés', recoveries: 'Récupérations', minutes: 'Minutes', goals: 'Buts',
  tileTouches: 'Touches', tileTopSpeed: 'Vit. max.', tileDuelsWon: 'Duels gag.', tileRecoveries: 'Récup.',
  mGoal: 'But', mAssist: 'Passe déc.', mYellow: 'Jaune', mRed: 'Rouge', mOff: 'Sort', mOn: 'Entre',
  corner: 'Corner', cornerFor: '{nth} corner pour {team}', fromLeft: 'De la gauche', fromRight: 'De la droite',
  eventData: 'Données d’événements', nearPost: 'Premier poteau', farPost: 'Second poteau', penaltySpot: 'Point de penalty', edgeOfBox: 'Entrée de la surface',
  short: 'Court', corners: 'Corners', left: 'Gauche', right: 'Droite', deliveryZone: 'Zone du centre', mainTarget: 'Cible principale',
  firstContacts: '{h}/{n} premiers contacts', noFirstContact: 'Aucun premier contact gagné', noCorners: 'Pas encore de corners',
  goalsFromCorners: 'Buts sur corner', thisMatch: 'Ce match', cupShort: 'Coupe',
  oHeader: 'Tête de {x}', oShot: 'Tir de {x}', oGoal: 'But', oCleared: 'Dégagé par {x}', oPlayedOut: 'Joué en retrait',
  oTo: 'vers {x}', oEdge: 'Joué à l’entrée de la surface', oShortTo: 'Corner à deux · joué vers {x}', oOffTarget: 'non cadré',
  oOnTarget: 'cadré', oSaved: 'arrêté', oBlocked: 'contré', oNotReached: 'Personne · sorti', oNoShot: 'pas de tir',
  oFirstContact: 'Premier contact {x}',
  // your view (favourite club and player)
  yourView: 'Votre vue',
  savedOnDevice: 'Enregistré sur cet appareil',
  profile: 'Votre vue : club, joueur, langue',
  club: 'Club',
  player: 'Joueur',
  viewLabel: 'Vue',
  neutral: 'Neutre',
  change: 'Changer',
  stopFollowing: 'Ne plus suivre',
  noPlayer: 'Aucun joueur suivi',
  choosePlayer: 'Choisir un joueur',
  resetNeutral: 'Revenir au neutre',
  followPlayer: 'Suivre le joueur',
  following: 'Suivi',
  yourClub: 'Votre club',
  filterAll: 'Tout',
  filterClub: 'Mon club',
  filterPlayer: 'Mon joueur',
  feedFilter: 'Afficher les cartes',
  stripOnPitch: 'Sur le terrain',
  cameOn: '{name} est entré',
  followName: 'Suivre {name}',
  stripBench: 'Sur le banc. Ses chiffres commencent à son entrée.',
  nowPlaying: 'Désormais {f}',
  showMore: 'Afficher plus',
  showLess: 'Afficher moins',
  km: 'Km',
  close: 'Fermer',
  // tactics per club
  clubView: 'Vue {club}',
  howToBeat: 'Comment battre {team}',
  changedToday: 'Ce que {team} a changé aujourd’hui',
  changedLabel: 'Changé',
  sameLabel: 'Pareil',
  tacticsView: 'Vue tactique',
  lever: 'Levier {n}',
};

export const DICTS: Record<Lang, Dict> = { en, nl, es, fr };

/** Role names from the line-up data, per language (fallback: the English name). */
export const ROLES: Record<Exclude<Lang, 'en'>, Record<string, string>> = {
  nl: { Goalkeeper: 'Doelman', 'Right-back': 'Rechtsback', 'Left-back': 'Linksback', 'Centre-back': 'Centrale verdediger',
    'Defensive midfield': 'Verdedigende middenvelder', 'Central midfield': 'Centrale middenvelder', 'Right midfield': 'Rechtermiddenvelder',
    'Left midfield': 'Linkermiddenvelder', 'Right wing': 'Rechtsbuiten', 'Left wing': 'Linksbuiten', Striker: 'Spits' },
  es: { Goalkeeper: 'Portero', 'Right-back': 'Lateral derecho', 'Left-back': 'Lateral izquierdo', 'Centre-back': 'Central',
    'Defensive midfield': 'Mediocentro defensivo', 'Central midfield': 'Mediocentro', 'Right midfield': 'Interior derecho',
    'Left midfield': 'Interior izquierdo', 'Right wing': 'Extremo derecho', 'Left wing': 'Extremo izquierdo', Striker: 'Delantero centro' },
  fr: { Goalkeeper: 'Gardien', 'Right-back': 'Latéral droit', 'Left-back': 'Latéral gauche', 'Centre-back': 'Défenseur central',
    'Defensive midfield': 'Milieu défensif', 'Central midfield': 'Milieu central', 'Right midfield': 'Milieu droit',
    'Left midfield': 'Milieu gauche', 'Right wing': 'Ailier droit', 'Left wing': 'Ailier gauche', Striker: 'Avant-centre' },
};

export const ordinals: Record<Lang, (n: number) => string> = {
  en: (n) => `${n}${n % 100 >= 11 && n % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] ?? 'th'}`,
  nl: (n) => `${n}e`,
  es: (n) => `${n}.º`,
  fr: (n) => (n === 1 ? '1er' : `${n}e`),
};

export type T = (key: Key, vars?: Record<string, string | number>) => string;

export function translator(lang: Lang): T {
  const d = DICTS[lang];
  return (key, vars) => {
    let s = d[key] ?? en[key];
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v));
    return s;
  };
}

/** Corner outcomes come from the event data as English phrases ("Header by #5 Dijkhuis · xG 0.03 · off target"). */
export function cornerOutcome(text: string, lang: Lang): string {
  if (lang === 'en') return text;
  const t = translator(lang);
  const zone: Record<string, Key> = { 'near post': 'nearPost', 'far post': 'farPost', 'penalty spot': 'penaltySpot', 'edge of the box': 'edgeOfBox', short: 'short' };
  const shot: Record<string, Key> = { 'off target': 'oOffTarget', 'on target': 'oOnTarget', saved: 'oSaved', blocked: 'oBlocked', 'no shot': 'oNoShot' };
  const part = (p: string): string => {
    let m: RegExpMatchArray | null;
    if ((m = p.match(/^(Header|Shot) by (.+)$/))) return t(m[1] === 'Header' ? 'oHeader' : 'oShot', { x: m[2] });
    if ((m = p.match(/^Cleared by (.+)$/))) return t('oCleared', { x: m[1] });
    if ((m = p.match(/^to (.+)$/))) return t('oTo', { x: m[1] });
    if ((m = p.match(/^played to (.+)$/))) return t('oTo', { x: m[1] });
    if ((m = p.match(/^First contact (.+)$/))) return t('oFirstContact', { x: m[1] });
    if ((m = p.match(/^(.+), (near post|far post|penalty spot|edge of the box)$/))) return `${m[1]}, ${t(zone[m[2]]).toLowerCase()}`;
    if (p === 'Played out') return t('oPlayedOut');
    if (p === 'Played to the edge of the box') return t('oEdge');
    if (p === 'Short corner') return t('oShortTo', { x: '' }).split(' · ')[0];
    if (p === 'Goal') return t('oGoal');
    if (p === 'Not reached') return t('oNotReached').split(' · ')[0];
    if (p === 'out of play') return t('oNotReached').split(' · ')[1];
    if (shot[p]) return t(shot[p]);
    return p;     // numbers, names, "xG 0.07": as they are
  };
  return text.split(' · ').map(part).join(' · ');
}

/**
 * What a card shows in the viewer's language:
 * - 'source'      English chosen, or the card is still analysing / streaming: the English text, no label;
 * - 'translated'  a checked translation: label "translated · checked", a click shows the English original;
 * - 'original'    the English original after that click;
 * - 'english'     no checked translation (rejected, too late, or on its way): the English text with label "EN".
 */
export type CardView = 'source' | 'translated' | 'original' | 'english';

export function cardView(lang: Lang, item: { phase?: string; translations?: Record<string, Translation> }, original: boolean): CardView {
  if (lang === 'en' || (item.phase && item.phase !== 'done')) return 'source';
  if (item.translations?.[lang]?.status === 'checked') return original ? 'original' : 'translated';
  return 'english';
}
