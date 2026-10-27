import type { TeamId } from './contracts';

/**
 * The viewer's own view of the match, per device (localStorage). Neutral is the default and changes nothing:
 * with club 'neutral' and no player, every helper below returns what the app did before.
 */
export type Preferences = {
  club: TeamId | 'neutral';
  /** one player at a time */
  playerId: string | null;
  stripCollapsed: boolean;
  /** phase B: the tactics card from the club's side, or the neutral original */
  tacticsView: 'club' | 'neutral';
  /** Casual fan | Analyst: the existing switch, now remembered too (default unchanged) */
  mode: 'casual' | 'analyst';
};

export const DEFAULT_PREFS: Preferences = { club: 'neutral', playerId: null, stripCollapsed: true, tacticsView: 'club', mode: 'casual' };
export const PREFS_KEY = 'itg-prefs';

/** Saved preferences, or the defaults for anything missing or broken. */
export function parsePrefs(raw: string | null | undefined): Preferences {
  if (!raw) return DEFAULT_PREFS;
  try {
    const v = JSON.parse(raw) as Partial<Preferences>;
    return {
      club: typeof v.club === 'string' && v.club ? v.club : DEFAULT_PREFS.club,
      playerId: typeof v.playerId === 'string' && v.playerId ? v.playerId : null,
      stripCollapsed: typeof v.stripCollapsed === 'boolean' ? v.stripCollapsed : DEFAULT_PREFS.stripCollapsed,
      tacticsView: v.tacticsView === 'neutral' ? 'neutral' : 'club',
      mode: v.mode === 'analyst' ? 'analyst' : 'casual',
    };
  } catch {
    return DEFAULT_PREFS;
  }
}

export type Emphasis = 'none' | 'mine' | 'opponent';

/** How a card about `team` is shown for this club: 'none' without a club, or for a card about nobody. */
export function emphasisOf(team: TeamId | undefined, club: Preferences['club']): Emphasis {
  if (club === 'neutral' || !team) return 'none';
  return team === club ? 'mine' : 'opponent';
}

/**
 * The club variant of a tactics card or scouting report to show, or null for the neutral card: only with a club,
 * in Analyst mode, with the club view on, and a checked variant for that club.
 */
export function perspectiveFor<P extends { status: string }>(
  perspectives: Record<string, P> | undefined, prefs: Pick<Preferences, 'club' | 'mode' | 'tacticsView'>,
): P | null {
  if (prefs.club === 'neutral' || prefs.mode !== 'analyst' || prefs.tacticsView !== 'club') return null;
  const p = perspectives?.[prefs.club];
  return p && p.status === 'checked' ? p : null;
}
