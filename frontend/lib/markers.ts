import type { Insight, Marker, MatchEvent } from './contracts';

/** Timeline markers: goals, cards and corrected claims. */
export function markersFrom(events: MatchEvent[], insights: Pick<Insight, 't' | 'minute' | 'status'>[]): Marker[] {
  const m: Marker[] = [];
  for (const e of events) {
    if (e.kind === 'goal') m.push({ t: e.t, minute: e.minute, kind: 'goal', team: e.team, title: `Goal ${e.text}` });
    if (e.kind === 'yellow') m.push({ t: e.t, minute: e.minute, kind: 'card', team: e.team, title: `Yellow card ${e.text}` });
    if (e.kind === 'red') m.push({ t: e.t, minute: e.minute, kind: 'red', team: e.team, title: `Red card ${e.text}` });
  }
  for (const i of insights) if (i.status === 'corrected') m.push({ t: i.t, minute: i.minute, kind: 'corrected', title: 'Claim corrected' });
  return m.sort((a, b) => a.t - b.t);
}
