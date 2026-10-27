'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { TeamId } from './contracts';
import { DEFAULT_PREFS, PREFS_KEY, emphasisOf, parsePrefs, type Emphasis, type Preferences } from './prefs';
import { useTeams } from './teams';

export type { Emphasis, Preferences } from './prefs';

type Ctx = {
  prefs: Preferences;
  set: (patch: Partial<Preferences>) => void;
  reset: () => void;
  /** follow this player (replaces the current one), or stop following with null */
  follow: (playerId: string | null) => void;
  isMyClub: (team?: TeamId) => boolean;
  isMyPlayer: (playerId?: string | null) => boolean;
  /** the club's colour as a CSS value, or undefined for Neutral */
  myClubColor: () => string | undefined;
  /** the other team of this match */
  opponentOf: (team: TeamId) => TeamId;
  emphasis: (team?: TeamId) => Emphasis;
};

const PrefsContext = createContext<Ctx | null>(null);

/** One store for the viewer's view, per device. First render = the defaults (Neutral), as on main. */
export function PreferencesProvider({ children }: { children: ReactNode }) {
  const teams = useTeams();
  const [prefs, setPrefs] = useState<Preferences>(DEFAULT_PREFS);
  useEffect(() => {
    try { setPrefs(parsePrefs(localStorage.getItem(PREFS_KEY))); } catch { /* storage blocked: defaults */ }
  }, []);
  const save = useCallback((next: Preferences) => {
    setPrefs(next);
    try { localStorage.setItem(PREFS_KEY, JSON.stringify(next)); } catch { /* storage blocked */ }
  }, []);
  const set = useCallback((patch: Partial<Preferences>) => setPrefs((p) => {
    const next = { ...p, ...patch };
    try { localStorage.setItem(PREFS_KEY, JSON.stringify(next)); } catch { /* storage blocked */ }
    return next;
  }), []);
  const value = useMemo<Ctx>(() => {
    const club = prefs.club === teams.home.id || prefs.club === teams.away.id ? prefs.club : 'neutral';
    return {
      prefs: { ...prefs, club },
      set,
      reset: () => save(DEFAULT_PREFS),
      follow: (playerId) => set({ playerId }),
      isMyClub: (team) => club !== 'neutral' && team === club,
      isMyPlayer: (id) => !!id && id === prefs.playerId,
      myClubColor: () => (club === 'neutral' ? undefined : teams.color(club)),
      opponentOf: (team) => (team === teams.home.id ? teams.away.id : teams.home.id),
      emphasis: (team) => emphasisOf(team, club),
    };
  }, [prefs, set, save, teams]);
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

/** Outside a provider (other pages): Neutral, and setters that do nothing. */
const NEUTRAL: Ctx = {
  prefs: DEFAULT_PREFS, set: () => {}, reset: () => {}, follow: () => {},
  isMyClub: () => false, isMyPlayer: () => false, myClubColor: () => undefined, opponentOf: (t) => t, emphasis: () => 'none',
};

export const usePreferences = () => useContext(PrefsContext) ?? NEUTRAL;
