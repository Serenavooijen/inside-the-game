/**
 * Contract between the frontend and the backend (FastAPI).
 *
 * The backend sends these shapes over SSE (`GET /stream`) and from `GET /state`.
 * Keep the Pydantic models in `backend/app/contracts.py` field-for-field in sync.
 *
 * Units: pitch positions in metres (x 0–105, y 0–68), absolute, as the generator
 * writes them (home attacks towards x = 105 in the first half, towards x = 0 in the
 * second). Match time `t` = generator frame = seconds of play since kick-off,
 * including added time (0 … duration). Display labels (clock, minute) come with it.
 */

/** Team id from the match data, e.g. "kba". Not a fixed list: every match brings its own teams. */
export type TeamId = string;
/** 1–2 halves, 3–4 extra time, 5 penalty shoot-out */
export type Period = 1 | 2 | 3 | 4 | 5;
export type Mode = 'live' | 'replay';
export type Speed = 1 | 10;

export type Point = { x: number; y: number };

export type Player = {
  id: string;
  team: TeamId;
  /** Shirt number */
  n: number;
  x: number;
  y: number;
  gk?: boolean;
  name?: string;
};

export type Frame = {
  t: number;
  players: Player[];
  ball: Point;
};

/** Fast lane: deterministic overlays, no LLM. Max one per slot on screen. */
export type OverlaySlot = 'tag' | 'pass' | 'shot' | 'sprint';

export type Overlay = {
  id: string;
  t: number;
  slot: OverlaySlot;
  playerId: string;
  /** pass: quality 0–1 · shot: xG · sprint: peak speed in km/h */
  value?: number;
  /** pass target or shot target */
  to?: Point;
  /** sprint: where the run started (draws the trail) */
  from?: Point;
  generation: number;
};

export type MatchEventKind = 'goal' | 'yellow' | 'red' | 'sub' | 'bigchance';

export type MatchEvent = {
  id: string;
  t: number;
  /** Football minute label, e.g. "24" or "45+2" */
  minute: string;
  kind: MatchEventKind;
  team: TeamId;
  /** The player involved (scorer, booked player) */
  playerId?: string;
  /** Short label for the scorebar, e.g. "Okafor 67'" */
  text: string;
  /** Sub-line for the key-moment bar, e.g. "Okafor (19) · assist Lindqvist (21)" */
  detail?: string;
  /** Key moments slow the match to 1× and show the hero card */
  key?: boolean;
};

/** Smart lane: agent output, checked against event data. */
export type InsightType = 'goal' | 'bigchance' | 'card' | 'momentum' | 'update' | 'fulltime';
export type InsightStatus = 'checked' | 'corrected' | 'fallback';
export type InsightPhase = 'analysing' | 'streaming' | 'done';
/** Area highlighted on the mini pitch (metres, absolute). */
export type Zone = {
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  /** optional dashed line at this x, e.g. the defensive line */
  line?: number;
  /** attacking direction of the team the insight is about: 1 = towards x 105 */
  dir?: 1 | -1;
};

export type CorrectionStats = {
  a: string;
  aLabel: string;
  aTeam: TeamId;
  b: string;
  bLabel: string;
  bTeam: TeamId;
};

export type Insight = {
  id: string;
  t: number;
  /** Football minute label, e.g. "24" or "90+3" */
  minute: string;
  /** id of the MatchEvent this insight explains, if any */
  momentId?: string;
  type: InsightType;
  /** type 'card': which card (default yellow) */
  card?: 'yellow' | 'red';
  team?: TeamId;
  /** Grows while phase = 'streaming' */
  text: string;
  status: InsightStatus;
  phase: InsightPhase;
  evidence: string[];
  zone?: Zone;
  /** status 'corrected': the agent's draft claim that failed the fact-check */
  claim?: string;
  stats?: CorrectionStats;
  analystStats?: { k: string; v: string }[];
  /** status 'fallback': why the template text was used */
  fallbackReason?: string;
  generation: number;
  /** Traceability from the agents (optional) */
  rejectedClaims?: { text: string; reason: string; factIds?: string[] }[];
  citedFactIds?: string[];
  latencyMs?: number;
  tokens?: number;
};

export type MatchStats = {
  score: [number, number];
  xg: [number, number];
  possession: [number, number];
};

/** Sent for every new match second. */
export type Tick = {
  t: number;
  period: Period;
  /** Match clock, e.g. "57:40" or "45+1:30" */
  clock: string;
  /** Football minute label, e.g. "58" or "45+2" */
  minute: string;
  speed: Speed;
  playing: boolean;
  /** Increases on every seek or reload. Drop overlays/insights with an older generation. */
  generation: number;
  frame: Frame;
  stats: MatchStats;
  /** Set while a key moment is on screen (the backend has slowed to 1×) */
  keyMomentId: string | null;
  finished: boolean;
};

export type Marker = {
  t: number;
  minute: string;
  kind: 'goal' | 'card' | 'red' | 'corrected';
  team?: TeamId;
  title: string;
};

/** Full picture, sent on (re)connect and from GET /state. */
export type MatchState = Tick & {
  matchId: string;
  mode: Mode;
  /** Last frame of the match (t at full time) */
  duration: number;
  /** First frame of the second half */
  halftime: number;
  events: MatchEvent[];
  insights: Insight[];
  /** Replay mode only: every marker for the whole match */
  markers?: Marker[];
};

export type StreamMessage =
  | { type: 'tick'; data: Tick }
  | { type: 'overlay'; data: Overlay }
  | { type: 'event'; data: MatchEvent }
  | { type: 'insight'; data: Insight }
  | { type: 'state'; data: MatchState };

export type TeamInfo = {
  id: string;
  name: string;
  short: string;
  color: string;
  fg: string;
};

export type MatchSummary = {
  id: string;
  home: TeamInfo;
  away: TeamInfo;
  score: string;
  story: string;
  meta: string;
  available: boolean;
};

