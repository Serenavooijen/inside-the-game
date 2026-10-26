'use client';

/**
 * Which team is home and which is away, for the match on screen.
 *
 * TeamId is a plain string from the match data ("kba", "hv", …). Components never
 * compare against fixed ids: they ask this module for the side, the name and the colours.
 */

import { createContext, useContext, useMemo, type ReactNode } from 'react';
import type { TeamId, TeamInfo } from './contracts';
import { MATCHES } from './matches';

export type Side = 'home' | 'away';

type Teams = { home: TeamInfo; away: TeamInfo };

const DEFAULT: Teams = { home: MATCHES[0].home, away: MATCHES[0].away };
const TeamsContext = createContext<Teams>(DEFAULT);

/** Teams of a match from the match list; falls back to the first match. */
export function teamsFor(matchId: string): Teams {
  const m = MATCHES.find((x) => x.id === matchId);
  return m ? { home: m.home, away: m.away } : DEFAULT;
}

export function TeamsProvider({ teams, children }: { teams: Teams; children: ReactNode }) {
  return <TeamsContext.Provider value={teams}>{children}</TeamsContext.Provider>;
}

export function useTeams() {
  const teams = useContext(TeamsContext);
  return useMemo(() => {
    const side = (id?: TeamId): Side | undefined => (id === teams.home.id ? 'home' : id === teams.away.id ? 'away' : undefined);
    const info = (id?: TeamId): TeamInfo | undefined => (id === teams.home.id ? teams.home : id === teams.away.id ? teams.away : undefined);
    return {
      ...teams,
      side,
      info,
      /** Fill colour as a CSS value (follows the CSS variables set by MatchScreen) */
      color: (id?: TeamId) => (side(id) === 'away' ? 'var(--itg-away)' : side(id) === 'home' ? 'var(--itg-home)' : 'var(--itg-fg-3)'),
      /** Readable text colour on the page background */
      text: (id?: TeamId) => (side(id) === 'away' ? 'var(--itg-away-text)' : side(id) === 'home' ? 'var(--itg-home-text)' : 'var(--itg-fg)'),
      /** Abbreviation on screen, e.g. "NTG": always the team's `short`, never derived from the team id */
      short: (id?: TeamId) => info(id)?.short ?? '',
      /** Short display name for TV bars, e.g. "Kingsbridge" */
      label: (id?: TeamId) => info(id)?.name.split(' ')[0] ?? '',
    };
  }, [teams]);
}

/** CSS variables for the team colours of this match (put on the screen's root element). */
export function teamColorVars(teams: Teams): Record<string, string> {
  return { '--itg-home': teams.home.color, '--itg-away': teams.away.color };
}
