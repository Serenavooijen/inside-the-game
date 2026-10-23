/**
 * Mock backend: behaves like the FastAPI backend so the frontend can be built and
 * demoed without it. It plays data/matches/kba-ngr.json (made from the output of
 * generate_match.py by scripts/import_generator.py) and pushes SSE messages in
 * exactly the shapes of lib/contracts.ts.
 *
 * Server-only. One global match session, like the real backend (1 replica).
 */
import fixtureJson from '@/data/matches/kba-ngr.json';
import type {
  Frame, Insight, Marker, MatchEvent, MatchState, MatchStats, Mode, Overlay,
  Player, Speed, StreamMessage, TeamId, Tick,
} from '@/lib/contracts';
import { markersFrom } from '@/lib/markers';

type RosterEntry = { id: string; team: TeamId; n: number; name: string; gk: boolean; on: [number, number][] };
type Fixture = {
  id: string;
  home: { id: TeamId; name: string; short: string };
  away: { id: TeamId; name: string; short: string };
  duration: number;
  halftime: number;
  roster: RosterEntry[];
  frames: number[][];
  events: MatchEvent[];
  overlays: Omit<Overlay, 'generation'>[];
  insights: Omit<Insight, 'generation' | 'phase'>[];
  stats: { t: number; xg: [number, number]; possession: [number, number] }[];
};
const fixture = fixtureJson as unknown as Fixture;
const END = fixture.duration;
const HT = fixture.halftime;

type Listener = (msg: StreamMessage) => void;

const TICK_MS = 50;
const ANALYSE_MS = 2000;
const WORD_MS = 150;
const FALLBACK_AFTER_MS = 6000;
const HOLD_AFTER_DONE_MS = 7000;

// ---------- clock helpers (same rules as generate_match.py) ----------
const pad = (n: number) => String(n).padStart(2, '0');
export function periodAt(t: number): 1 | 2 { return t < HT ? 1 : 2; }
export function clockAt(t: number) {
  const p = periodAt(t);
  const s = Math.floor(p === 1 ? t : t - HT);
  const base = p === 1 ? 0 : 2700;
  if (s < 2700) { const tot = base + s; return `${pad(Math.floor(tot / 60))}:${pad(tot % 60)}`; }
  const extra = s - 2700;
  return `${p === 1 ? 45 : 90}+${Math.floor(extra / 60)}:${pad(extra % 60)}`;
}
export function minuteAt(t: number) {
  const p = periodAt(t);
  const s = Math.floor(p === 1 ? t : t - HT);
  if (s < 2700) return String(Math.floor(((p === 1 ? 0 : 2700) + s) / 60) + 1);
  return `${p === 1 ? 45 : 90}+${Math.floor((s - 2700) / 60) + 1}`;
}

class MockMatch {
  matchId = fixture.id;
  mode: Mode = 'live';
  t = 0;
  speed: Speed = 10;
  playing = false;
  generation = 1;
  keyMomentId: string | null = null;
  private speedBeforeKey: Speed = 10;
  private listeners = new Set<Listener>();
  private timers = new Set<ReturnType<typeof setTimeout>>();
  private live = new Map<string, Insight>();
  private lastSecond = 0;
  private loop: ReturnType<typeof setInterval> | null = null;
  private lastReal = Date.now();

  // ---------- lifecycle ----------
  load(matchId: string, mode: Mode) {
    if (matchId !== fixture.id) throw new Error(`Unknown match: ${matchId}`);
    this.mode = mode;
    this.reset(0);
    this.playing = true;
    this.speed = 10;
    this.ensureLoop();
    this.broadcastState();
  }

  subscribe(fn: Listener) {
    this.listeners.add(fn);
    this.ensureLoop();
    return () => { this.listeners.delete(fn); };
  }

  play() { if (this.t >= END) this.reset(0); this.playing = true; this.emitTick(); }
  pause() { this.playing = false; this.emitTick(); }
  setSpeed(s: Speed) {
    if (this.keyMomentId) this.speedBeforeKey = s; else this.speed = s;
    if (!this.keyMomentId) this.emitTick();
  }
  seek(t: number) {
    this.reset(Math.round(Math.max(0, Math.min(END, t))));
    this.broadcastState();
  }

  // ---------- state ----------
  private reset(t: number) {
    for (const x of this.timers) clearTimeout(x);
    this.timers.clear();
    this.live.clear();
    if (this.keyMomentId) this.speed = this.speedBeforeKey;
    this.keyMomentId = null;
    this.t = t;
    this.lastSecond = Math.floor(t);
    this.generation += 1;
  }

  private ensureLoop() {
    if (this.loop) return;
    this.lastReal = Date.now();
    this.loop = setInterval(() => this.step(), TICK_MS);
  }

  private step() {
    const now = Date.now();
    const dt = (now - this.lastReal) / 1000;
    this.lastReal = now;
    if (!this.playing || this.t >= END) return;
    const prev = this.t;
    this.t = Math.min(END, this.t + dt * this.speed);
    this.process(prev, this.t);
    const sec = Math.floor(this.t);
    if (sec !== this.lastSecond) { this.lastSecond = sec; this.emitTick(); }
    if (this.t >= END) { this.playing = false; this.emitTick(); }
  }

  /** Everything scheduled in (from, to]. */
  private process(from: number, to: number) {
    const inRange = (t: number) => t > from && t <= to;
    for (const e of fixture.events) if (inRange(e.t)) {
      this.send({ type: 'event', data: e });
      if (e.key) this.startKeyMoment(e.id);
    }
    for (const o of fixture.overlays) if (inRange(o.t)) this.send({ type: 'overlay', data: { ...o, generation: this.generation } });
    for (const i of fixture.insights) if (inRange(i.t)) this.runInsight(i);
  }

  private startKeyMoment(id: string) {
    if (this.keyMomentId) return;
    this.keyMomentId = id;
    this.speedBeforeKey = this.speed;
    this.speed = 1;
    this.emitTick();
    // Safety net: never stay slowed for more than 25 s
    this.later(() => this.endKeyMoment(id), 25000);
  }

  private endKeyMoment(id: string) {
    if (this.keyMomentId !== id) return;
    this.keyMomentId = null;
    this.speed = this.speedBeforeKey;
    this.emitTick();
  }

  /** Simulates the agent workflow: analysing → streaming → done (or fallback). */
  private runInsight(base: Omit<Insight, 'generation' | 'phase'>) {
    const gen = this.generation;
    const full: Insight = { ...base, phase: 'done', generation: gen };
    const isHero = !!base.momentId && base.momentId === this.keyMomentId;
    const finish = () => {
      this.live.delete(base.id);
      this.send({ type: 'insight', data: full });
      if (isHero) this.later(() => this.endKeyMoment(base.momentId!), HOLD_AFTER_DONE_MS);
    };
    if (this.mode === 'replay') {
      // Recorded run: no model calls, the text is shown as recorded.
      this.later(finish, isHero ? 600 : 0);
      return;
    }
    const analysing: Insight = { ...full, phase: 'analysing', text: '' };
    this.live.set(base.id, analysing);
    this.send({ type: 'insight', data: analysing });
    if (base.status === 'fallback') {
      this.later(finish, FALLBACK_AFTER_MS);
      return;
    }
    const words = base.text.split(' ');
    words.forEach((_, i) => {
      this.later(() => {
        const partial: Insight = { ...full, phase: 'streaming', text: words.slice(0, i + 1).join(' ') };
        this.live.set(base.id, partial);
        this.send({ type: 'insight', data: partial });
      }, ANALYSE_MS + i * WORD_MS);
    });
    this.later(finish, ANALYSE_MS + words.length * WORD_MS + 300);
  }

  /** Timers are cancelled on seek; callbacks from an old generation never run. */
  private later(fn: () => void, ms: number) {
    const gen = this.generation;
    const h = setTimeout(() => { this.timers.delete(h); if (gen === this.generation) fn(); }, ms);
    this.timers.add(h);
  }

  // ---------- derived data ----------
  frameAt(t: number): Frame {
    const i = Math.max(0, Math.min(fixture.frames.length - 1, Math.floor(t)));
    const row = fixture.frames[i];
    const players: Player[] = [];
    let k = 2;
    for (const p of fixture.roster) {
      if (!p.on.some(([a, b]) => i >= a && i <= b)) continue;
      players.push({ id: p.id, team: p.team, n: p.n, name: p.name, gk: p.gk, x: row[k], y: row[k + 1] });
      k += 2;
    }
    return { t: i, players, ball: { x: row[0], y: row[1] } };
  }

  statsAt(t: number): MatchStats {
    const s = fixture.stats;
    let j = s.findIndex((x) => x.t > t);
    if (j === -1) j = s.length - 1;
    const a = s[Math.max(0, j - 1)], b = s[j];
    const k = b.t === a.t ? 1 : Math.max(0, Math.min(1, (t - a.t) / (b.t - a.t)));
    const l = (x: number, y: number) => x + (y - x) * k;
    const goals = fixture.events.filter((e) => e.kind === 'goal' && e.t <= t);
    return {
      score: [goals.filter((g) => g.team === fixture.home.id).length, goals.filter((g) => g.team === fixture.away.id).length],
      xg: [Math.round(l(a.xg[0], b.xg[0]) * 100) / 100, Math.round(l(a.xg[1], b.xg[1]) * 100) / 100],
      possession: [Math.round(l(a.possession[0], b.possession[0])), Math.round(l(a.possession[1], b.possession[1]))],
    };
  }

  tick(): Tick {
    const t = Math.floor(this.t);
    return {
      t,
      period: periodAt(t),
      clock: clockAt(t),
      minute: minuteAt(t),
      speed: this.speed,
      playing: this.playing,
      generation: this.generation,
      frame: this.frameAt(t),
      stats: this.statsAt(t),
      keyMomentId: this.keyMomentId,
      finished: this.t >= END,
    };
  }

  state(): MatchState {
    const t = this.t;
    const insights: Insight[] = fixture.insights
      .filter((i) => i.t <= t && !this.live.has(i.id))
      .map((i) => ({ ...i, phase: 'done' as const, generation: this.generation }));
    for (const i of this.live.values()) insights.push(i);
    insights.sort((a, b) => a.t - b.t);
    const state: MatchState = {
      ...this.tick(),
      matchId: this.matchId,
      mode: this.mode,
      duration: END,
      halftime: HT,
      events: fixture.events.filter((e) => e.t <= t),
      insights,
    };
    if (this.mode === 'replay') state.markers = allMarkers();
    return state;
  }

  // ---------- transport ----------
  private emitTick() { this.send({ type: 'tick', data: this.tick() }); }
  private broadcastState() { this.send({ type: 'state', data: this.state() }); }
  private send(msg: StreamMessage) { for (const fn of this.listeners) fn(msg); }
}

function allMarkers(): Marker[] {
  return markersFrom(fixture.events, fixture.insights);
}

const g = globalThis as unknown as { __itgMock?: MockMatch };
export const mockMatch: MockMatch = g.__itgMock ?? (g.__itgMock = new MockMatch());
