import type { Insight } from './contracts';
import type { Corner } from './lineups';

export type FeedItem = { kind: 'insight'; t: number; insight: Insight } | { kind: 'corner'; t: number; corner: Corner };

/** How many agent cards the feed keeps (newest first). */
export const MAX_INSIGHTS = 14;

/**
 * The feed: moment, tactics, substitution and corner cards together, newest first.
 *
 * The limit applies to the insight cards only. Corner cards are made by code from the event data
 * and are few (one per corner), so they never push a tactics, substitution or moment card out.
 * Tactics cards show in Analyst mode only.
 */
export function feedItems(insights: Insight[], corners: Corner[], mode: 'casual' | 'analyst'): FeedItem[] {
  const cards = insights
    .filter((i) => mode === 'analyst' || i.type !== 'tactics')
    .sort((a, b) => b.t - a.t)
    .slice(0, MAX_INSIGHTS)
    .map((i): FeedItem => ({ kind: 'insight', t: i.t, insight: i }));
  // At equal t the insight goes first, so a moment card stays above a corner in the same second.
  return [...cards, ...corners.map((c): FeedItem => ({ kind: 'corner', t: c.t, corner: c }))]
    .sort((a, b) => b.t - a.t || (a.kind === b.kind ? 0 : a.kind === 'insight' ? -1 : 1));
}
