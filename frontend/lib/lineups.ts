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
  /** [from t, {player id: role}] per team, e.g. "RCB" */
  roles: Record<TeamId, [number, Record<string, string>][]>;
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

// ---------------------------------------------------------------- formation view

// Depth from the own goal (1 = back line … 5 = front line) and side (-1 left … +1 right) per role.
// Wing-backs sit between the back line and midfield, so a 5-4-1 and a 3-4-2 both split correctly.
const DEPTH: Record<string, number> = {
  GK: 0, RB: 1, RCB: 1, CB: 1, LCB: 1, LB: 1, DM: 2, RWB: 2.5, LWB: 2.5,
  RM: 3, RCM: 3, CM: 3, LCM: 3, LM: 3, AM: 4, RW: 5, RS: 5, ST: 5, LS: 5, LW: 5, FW: 5,
};
const SIDE: Record<string, number> = {
  RB: 1, RWB: 1, RM: 1, RW: 1, RCB: 0.4, RCM: 0.4, RS: 0.4, LCB: -0.4, LCM: -0.4, LS: -0.4, LB: -1, LWB: -1, LM: -1, LW: -1,
};
const DEFENDERS = new Set(['RB', 'RCB', 'CB', 'LCB', 'LB', 'RWB', 'LWB']);

/** The role of every player of a team at match second t (tactical states; a substitute without one takes the role of the player he replaced). */
export function rolesAt(l: Lineups, team: TeamId, t: number): Record<string, string> {
  const snap = [...(l.roles[team] ?? [])].reverse().find(([from]) => from <= t)?.[1] ?? {};
  const out: Record<string, string> = {};
  for (const p of l.players) {
    if (p.team !== team || statusAt(p, t) !== 'on') continue;
    const replaced = p.replaced ? snap[p.replaced] : undefined;
    out[p.id] = snap[p.id] ?? replaced ?? p.role;
  }
  return out;
}

/**
 * The classic line-up on the own half (attacking left to right): goalkeeper at the own goal, then
 * the lines of the current formation, each spread over the width (left side at the top).
 * Only players on the pitch now; when the shape does not add up (e.g. just after a red card)
 * the lines follow the roles.
 */
export function formationSpots(l: Lineups, team: TeamId, t: number): { id: string; x: number; y: number }[] {
  const roles = rolesAt(l, team, t);
  const ids = Object.keys(roles);
  const gk = ids.filter((id) => roles[id] === 'GK');
  const field = ids.filter((id) => roles[id] !== 'GK')
    .sort((a, b) => (DEPTH[roles[a]] ?? 3) - (DEPTH[roles[b]] ?? 3) || (SIDE[roles[a]] ?? 0) - (SIDE[roles[b]] ?? 0));
  const shape = formationAt(l, team, t).split('-').map(Number).filter((n) => n > 0);
  let lines: string[][] = [];
  if (shape.reduce((a, b) => a + b, 0) === field.length) {
    let k = 0;
    lines = shape.map((n) => field.slice(k, (k += n)));
  } else {
    const band = (id: string) => { const d = DEPTH[roles[id]] ?? 3; return d < 2 ? 0 : d < 5 ? 1 : 2; };
    lines = [0, 1, 2].map((b) => field.filter((id) => band(id) === b)).filter((x) => x.length);
  }
  const spots = gk.map((id) => ({ id, x: 5, y: 34 }));
  lines.forEach((line, i) => {
    const x = lines.length === 1 ? 30 : 16 + (i * (46 - 16)) / (lines.length - 1);
    [...line].sort((a, b) => (SIDE[roles[a]] ?? 0) - (SIDE[roles[b]] ?? 0))
      .forEach((id, k) => spots.push({ id, x, y: (68 * (k + 1)) / (line.length + 1) }));
  });
  return spots;
}

/** Average distance of the back line from the own goal (m), from the average positions so far. */
export function lineHeight(l: Lineups, team: TeamId, t: number): number | null {
  const roles = rolesAt(l, team, t);
  const xs = l.players
    .filter((p) => DEFENDERS.has(roles[p.id] ?? ''))
    .map((p) => average(samples(l, p, p.on![0], endAt(p, t)))?.x)
    .filter((x): x is number => x !== undefined);
  return xs.length ? Math.round(xs.reduce((a, b) => a + b, 0) / xs.length) : null;
}


/** Both teams on one pitch, as a TV line-up: the home team on the left half (keeper at the left goal),
 *  the away team turned round on the right half (keeper at the right goal). Each team stays in its own half. */
export function formationBoth(l: Lineups, home: TeamId, away: TeamId, t: number): { id: string; team: TeamId; x: number; y: number }[] {
  return [
    ...formationSpots(l, home, t).map((s) => ({ ...s, team: home })),
    ...formationSpots(l, away, t).map((s) => ({ ...s, team: away, x: 105 - s.x, y: 68 - s.y })),
  ];
}

// ---------------------------------------------------------------- player focus

export type PlayerFocus = {
  player: LineupPlayer;
  status: Status;
  /** live numbers up to t (final numbers once he is off); null on the bench */
  stats: PlayerStats | null;
  /** status 'off': the substitute who came on for him */
  replacedBy?: LineupPlayer;
  /** status 'red': his team's formation now, from the line-up data */
  formationAfter?: string;
};

/** Everything the followed player's strip shows at t, from the line-up data (nothing is made up). */
export function playerFocus(l: Lineups, id: string, t: number): PlayerFocus | null {
  const player = l.players.find((p) => p.id === id);
  if (!player) return null;
  const status = statusAt(player, t);
  return {
    player, status, stats: statsAt(l, player, t),
    replacedBy: status === 'off' && player.off?.by ? l.players.find((p) => p.id === player.off!.by) : undefined,
    formationAfter: status === 'red' ? formationAt(l, player.team, t) : undefined,
  };
}
