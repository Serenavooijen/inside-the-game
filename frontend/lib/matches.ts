import type { MatchSummary } from './contracts';

/** Shown on the start screen. Only matches with `available: true` have a recording. */
export const MATCHES: MatchSummary[] = [
  {
    id: 'kba-ngr',
    home: { id: 'kba', name: 'Kingsbridge Athletic', short: 'KBA', color: '#2F6BFF', fg: '#FFFFFF' },
    away: { id: 'ngr', name: 'Northgate Rovers', short: 'NGR', color: '#FFB400', fg: '#121212' },
    score: '2–2',
    story: 'Kingsbridge had the ball and the xG (2.48 – 1.52), then lost Brannigan to a second yellow. Northgate led twice; a substitute’s header made it 2-2.',
    meta: '4-3-3 vs 4-4-2 · 4 goals · 1 red card · 1 claim corrected',
    available: true,
  },
  {
    id: 'hv-su',
    home: { id: 'hv', name: 'Harlow Vale', short: 'HV', color: '#8E2A3B', fg: '#FFFFFF' },
    away: { id: 'su', name: 'Saltmarsh United', short: 'SU', color: '#1E8C8C', fg: '#FFFFFF' },
    score: '1–0',
    story: "One shot on target in the first hour. Saltmarsh's back five held until a corner in the 78th minute.",
    meta: '4-2-3-1 vs 5-3-2 · 3 key moments',
    available: false,
  },
  {
    id: 'et-cc',
    home: { id: 'et', name: 'Eastbrook Town', short: 'ET', color: '#E8E4DD', fg: '#121212' },
    away: { id: 'cc', name: 'Calder City', short: 'CC', color: '#6A4BC4', fg: '#FFFFFF' },
    score: '3–1',
    story: 'Calder pressed high and led at the break. Eastbrook scored twice in four minutes after it.',
    meta: '4-4-2 vs 4-3-3 · 7 key moments',
    available: false,
  },
  {
    id: 'pfc-aw',
    home: { id: 'pfc', name: 'Penford FC', short: 'PFC', color: '#202020', fg: '#FFFFFF' },
    away: { id: 'aw', name: 'Ashworth Wanderers', short: 'AW', color: '#C8501E', fg: '#FFFFFF' },
    score: '0–0',
    story: 'Two red cards, no goals. Both sides finished with ten men and one shot each after the 70th minute.',
    meta: '3-4-3 vs 4-1-4-1 · 4 key moments',
    available: false,
  },
];
