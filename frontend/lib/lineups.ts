'use client';

/**
 * Line-ups, player numbers over time, positions and corners of a match.
 *
 * Built by scripts/build_lineups.py from the generator output: every number is measured by
 * code. The frontend only slices it at the current match second, so it works the same for the
 * mock and the real backend, live and after a seek.
 *
 * Positions are team-relative: the team always attacks left to right (x 0 → 105).
 */

import { useEffect, useState } from 'react';
import type { TeamId } from './contracts';

export type MomentKind = 'goal' | 'assist' | 'yellow' | 'red' | 'on' | 'off';

export type LineupPlayer = {
  id: string;
  team: TeamId;
  n: number;
  name: string;
  gk: boolean;
  /** e.g. "CM" */
  role: string;
  /** e.g. "Central midfield" */
  roleName: string;
  starter: boolean;
  /** [first, last] match second on the pitch; null = never played */
  on: [number, number] | null;
  off: { t: number; minute: string; reason: 'sub' | 'red'; by?: string } | null;
  /** came on for this player */
  replaced: string | null;
  /** [t, minute label, kind] */
  moments: [number, string, MomentKind][];
  /** times of: T touch, P/p pass completed/failed, D/d duel won/lost, R recovery; S = [t, xG] */
  acts: { T?: number[]; P?: number[]; p?: number[]; D?: number[]; d?: number[]; R?: number[]; S?: [number, number][] };
  sprints: number[];
  /** [t, km/h] every time the top speed rises */
  tops: [number, number][];
  /** distance in metres per bucket (10 s), from bucket d0 */
  d0: number;
  dist: number[];
  /** positions every `sample` seconds from sample s0: [x, y, x, y, …], team-relative */
  s0: number;
  xy: number[];
};

export type CornerPlayer = { n: number; u: number; v: number; id: string; gk?: boolean; height?: number };

/** Positions at the moment of delivery, always stored as a corner from the left:
 *  u 0–68 along the goal line, v = distance from the goal line. */
export type Corner = {
  id: string;
  t: number;
  minute: string;
  team: TeamId;
  nth: number;
  side: 'left' | 'right';
  taker: number;
  takerId: string;
  attackers: CornerPlayer[];
  defenders: CornerPlayer[];
  firstTouch: { u: number; v: number; n: number | null; id: string | null; team: TeamId | null };
  zone: 'near' | 'far' | 'spot' | 'short';
  outcome: { kind: 'header' | 'shot' | 'cleared' | 'short' | 'goal'; text: string; xg?: number };
};

export type Lineups = {
  matchId: string;
  duration: number;
  halftime: number;
  sample: number;
  bucket: number;
  /** [from t, shape] per team */
  formations: Record<TeamId, [number, string][]>;
  players: LineupPlayer[];
  corners: Corner[];
  cup: { cornerGoals: Record<TeamId, number> } | null;
};

const SOURCES: Record<string, () => Promise<{ default: unknown }>> = {
  'kba-ngr': () => import('@/data/lineups/kba-ngr.json'),
};

/** Loads the line-ups of a match in its own chunk; null while loading or when the match has none. */
export function useLineups(matchId: string): Lineups | null {
  const [data, setData] = useState<Lineups | null>(null);
  useEffect(() => {
    let live = true;
    setData(null);
    SOURCES[matchId]?.().then((m) => { if (live) setData(m.default as Lineups); }).catch(() => {});
    return () => { live = false; };
  }, [matchId]);
  return data;
}

/** Football minute of a match second, as the clock and the events show it (68:11 is the 69th minute). */
function footballMinute(t: number, halftime: number): [number, number] {
  return t < halftime ? [Math.floor(t / 60) + 1, 45] : [45 + Math.floor((t - halftime) / 60) + 1, 90];
}

/** Minute label, e.g. "45+2" or "69"; kick-off is "0" so ranges read "0–69'". */
export function minuteAt(t: number, halftime: number): string {
  if (t <= 0) return '0';
  const [m, cap] = footballMinute(t, halftime);
  return m <= cap ? String(m) : `${cap}+${m - cap}`;
}

/** Minutes played between two match seconds, counted in football minutes without added time. */
export function minutesBetween(a: number, b: number, halftime: number): number {
  // the second half starts at 45:00, so a half-time substitute plays 45 minutes
  const m = (t: number) => (t <= 0 ? 0 : t === halftime ? 45 : Math.min(...footballMinute(t, halftime)));
  return Math.max(0, m(b) - m(a));
}

export type Status = 'on' | 'off' | 'red' | 'bench';

/** Where the player is at match second t. A substitute who has not come on yet is on the bench. */
export function statusAt(p: LineupPlayer, t: number): Status {
  if (!p.on || p.on[0] > t) return 'bench';
  if (p.off && p.off.t <= t) return p.off.reason === 'red' ? 'red' : 'off';
  return 'on';
}

/** Last match second that counts for the player: now, or the moment he left. */
export const endAt = (p: LineupPlayer, t: number) => (p.on ? Math.min(t, p.off && p.off.t <= t ? p.off.t : p.on[1]) : 0);

export const formationAt = (l: Lineups, team: TeamId, t: number) => {
  const list = l.formations[team] ?? [];
  return [...list].reverse().find(([from]) => from <= t)?.[1] ?? list[0]?.[1] ?? '';
};

const upTo = (xs: number[] | undefined, t: number) => (xs ?? []).filter((x) => x <= t).length;

export type PlayerStats = {
  touches: number; passes: number; attempts: number; shots: number; xg: number;
  sprints: number; km: number; top: number; duelsWon: number; duels: number; recoveries: number;
};

/** The stat tiles at match second t. Live numbers step every bucket (10 s); after leaving they stay frozen. */
export function statsAt(l: Lineups, p: LineupPlayer, t: number): PlayerStats | null {
  if (!p.on || p.on[0] > t) return null;
  const end = endAt(p, t);
  const T = p.off && p.off.t <= t ? end : Math.floor(end / l.bucket) * l.bucket;
  const a = p.acts;
  const shots = (a.S ?? []).filter(([s]) => s <= T);
  const buckets = Math.max(0, Math.floor(T / l.bucket) - p.d0 + 1);
  const passes = upTo(a.P, T);
  const duelsWon = upTo(a.D, T);
  return {
    touches: upTo(a.T, T),
    passes,
    attempts: passes + upTo(a.p, T),
    shots: shots.length,
    xg: shots.reduce((s, [, x]) => s + x, 0),
    sprints: upTo(p.sprints, T),
    km: p.dist.slice(0, buckets).reduce((s, d) => s + d, 0) / 1000,
    top: [...p.tops].reverse().find(([s]) => s <= T)?.[1] ?? 0,
    duelsWon,
    duels: duelsWon + upTo(a.d, T),
    recoveries: upTo(a.R, T),
  };
}

/** Positions on the pitch between two match seconds. */
export function samples(l: Lineups, p: LineupPlayer, from: number, to: number): { x: number; y: number }[] {
  const out: { x: number; y: number }[] = [];
  for (let k = 0; k < p.xy.length / 2; k++) {
    const s = (p.s0 + k) * l.sample;
    if (s < from) continue;
    if (s > to) break;
    out.push({ x: p.xy[2 * k], y: p.xy[2 * k + 1] });
  }
  return out;
}

export function average(pts: { x: number; y: number }[]) {
  if (!pts.length) return null;
  return { x: pts.reduce((s, q) => s + q.x, 0) / pts.length, y: pts.reduce((s, q) => s + q.y, 0) / pts.length };
}

export const HEAT_COLS = 21;
export const HEAT_ROWS = 14;
const STEPS = [0.14, 0.3, 0.5, 0.7, 0.9];

/** Heatmap cells (21 × 14, 5 m) as opacity steps: less than 14% of the maximum stays empty. */
export function heatCells(pts: { x: number; y: number }[]): number[] {
  const raw = new Array(HEAT_COLS * HEAT_ROWS).fill(0);
  for (const q of pts) {
    const c = Math.min(HEAT_COLS - 1, Math.max(0, Math.floor(q.x / 5)));
    const r = Math.min(HEAT_ROWS - 1, Math.max(0, Math.floor(q.y / (68 / HEAT_ROWS))));
    // a light blur so one sample is not one hard square
    for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) {
      const rr = r + dr, cc = c + dc;
      if (rr < 0 || rr >= HEAT_ROWS || cc < 0 || cc >= HEAT_COLS) continue;
      raw[rr * HEAT_COLS + cc] += dr === 0 && dc === 0 ? 1 : 0.35;
    }
  }
  const max = Math.max(...raw) || 1;
  return raw.map((v) => {
    const k = v / max;
    return k < 0.14 ? 0 : k < 0.3 ? STEPS[0] : k < 0.5 ? STEPS[1] : k < 0.7 ? STEPS[2] : k < 0.88 ? STEPS[3] : STEPS[4];
  });
}

export const ZONE_LABEL: Record<Corner['zone'], string> = { near: 'Near post', far: 'Far post', spot: 'Penalty spot', short: 'Short' };

/** "4th" */
export const ordinal = (n: number) => `${n}${n % 100 >= 11 && n % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] ?? 'th'}`;
