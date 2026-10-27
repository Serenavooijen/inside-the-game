import type { Insight, TeamId } from './contracts';
import type { Corner } from './lineups';
import type { Preferences } from './prefs';

export type FeedItem = { kind: 'insight'; t: number; insight: Insight } | { kind: 'corner'; t: number; corner: Corner };

/** How many agent cards the feed keeps (newest first). */
export const MAX_INSIGHTS = 14;

/**
 * The feed: moment, tactics, substitution and corner cards together, newest first.
 *
 * The limit applies to the insight cards only. Corner cards are made by code from the event data
 * and are few (one per corner), so they never push a tactics, substitution or moment card out.
 * Tactics cards show in Analyst mode only. `sel` (My club, My player) narrows the cards first, so the same
 * rules hold within it; without it, or with 'all', nothing changes.
 */
export function feedItems(allInsights: Insight[], allCorners: Corner[], mode: 'casual' | 'analyst', sel?: FeedSelection): FeedItem[] {
  const [insights, corners] = applyFeedFilter(allInsights, allCorners, sel);
  const cards = insights
    .filter((i) => mode === 'analyst' || i.type !== 'tactics')
    .sort((a, b) => b.t - a.t)
    .slice(0, MAX_INSIGHTS)
    .map((i): FeedItem => ({ kind: 'insight', t: i.t, insight: i }));
  // At equal t the insight goes first, so a moment card stays above a corner in the same second.
  return [...cards, ...corners.map((c): FeedItem => ({ kind: 'corner', t: c.t, corner: c }))]
    .sort((a, b) => b.t - a.t || (a.kind === b.kind ? 0 : a.kind === 'insight' ? -1 : 1));
}

// ---------------------------------------------------------------- My club, My player

/** The team a card is about: its team, the substitution's team, or the team of its first observation. */
export function insightTeam(i: Insight): TeamId | undefined {
  return i.team ?? i.substitution?.team ?? i.observations?.find((o) => o.team)?.team ?? undefined;
}

export type FeedFilter = 'all' | 'club' | 'player';
export type FocusPlayer = { id: string; name: string };

/** "D. Duarte" -> "Duarte"; "T. Ferreira-Lind" -> "Ferreira-Lind". */
export const surname = (name: string) => name.split('. ').pop() ?? name;

/**
 * Does the card mention this player? By id (substitutions) or by surname in the English text, evidence,
 * observations or watch points. Assumption: surnames are unique within the match (true for this match's data).
 */
export function mentionsPlayer(i: Insight, p: FocusPlayer): boolean {
  const s = i.substitution;
  if (s && [...s.off, ...s.on].some((x) => x.playerId === p.id)) return true;
  const rx = new RegExp(`(?<![\\p{L}-])${surname(p.name).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![\\p{L}-])`, 'u');
  const texts = [i.text, i.claim ?? '', ...(i.evidence ?? []), ...(s?.watch ?? []),
    ...(i.observations ?? []).flatMap((o) => [o.observation, o.consequence, o.coachAction ?? ''])];
  return texts.some((t) => rx.test(t));
}

/** Corners the player took part in: taker, first contact, or in the box at the delivery. */
export function cornerHasPlayer(c: Corner, id: string): boolean {
  return c.takerId === id || c.firstTouch.id === id || [...c.attackers, ...c.defenders].some((x) => x.id === id);
}

export type FeedSelection = { filter: FeedFilter; club: Preferences['club']; player: FocusPlayer | null };

/** The insights and corners a feed filter keeps; 'all' (and a filter without a choice) keeps everything. */
export function applyFeedFilter(insights: Insight[], corners: Corner[], sel?: FeedSelection): [Insight[], Corner[]] {
  if (!sel || sel.filter === 'all') return [insights, corners];
  if (sel.filter === 'club' && sel.club !== 'neutral') {
    return [insights.filter((i) => insightTeam(i) === sel.club), corners.filter((c) => c.team === sel.club)];
  }
  if (sel.filter === 'player' && sel.player) {
    const p = sel.player;
    return [insights.filter((i) => mentionsPlayer(i, p)), corners.filter((c) => cornerHasPlayer(c, p.id))];
  }
  return [insights, corners];
}
