import { memo } from 'react';
import type { Player, Point, TeamInfo } from '@/lib/contracts';
import { useTeams } from '@/lib/teams';
import { Ball } from './icons';

/** Metres (x 0–105, y 0–68) to CSS percentages inside the pitch box (viewBox -3 -3 111 74). */
export const pct = (p: Point) => ({ left: `${((p.x + 3) / 111) * 100}%`, top: `${((p.y + 3) / 74) * 100}%` });

const STRIPES = [4.93, 20.79, 36.64, 52.5, 68.36, 84.21, 100.07];

/** Grass, chalk lines and goals. Static, so memoised. */
export const PitchSurface = memo(function PitchSurface() {
  return (
    <svg viewBox="-3 -3 111 74" className="absolute inset-0 block h-full w-full" aria-hidden>
      <defs>
        <radialGradient id="itgLamp" cx="50%" cy="45%" r="70%">
          <stop offset="0" stopColor="#fff" stopOpacity=".10" />
          <stop offset=".55" stopColor="#fff" stopOpacity="0" />
          <stop offset="1" stopColor="#000" stopOpacity=".38" />
        </radialGradient>
        <pattern id="itgNet" width="0.8" height="0.8" patternUnits="userSpaceOnUse">
          <path d="M0 0L.8 .8M.8 0L0 .8" stroke="#fff" strokeWidth=".08" strokeOpacity=".7" />
        </pattern>
      </defs>
      <rect x="-3" y="-3" width="111" height="74" fill="var(--itg-grass-a)" />
      <g fill="var(--itg-grass-b)">
        {STRIPES.map((x) => <rect key={x} x={x} y="-3" width="7.93" height="74" />)}
      </g>
      <g fill="none" stroke="#fff" strokeOpacity=".88" strokeWidth=".22">
        <rect x="0" y="0" width="105" height="68" />
        <line x1="52.5" y1="0" x2="52.5" y2="68" />
        <circle cx="52.5" cy="34" r="9.15" />
        <rect x="0" y="13.84" width="16.5" height="40.32" />
        <rect x="88.5" y="13.84" width="16.5" height="40.32" />
        <rect x="0" y="24.84" width="5.5" height="18.32" />
        <rect x="99.5" y="24.84" width="5.5" height="18.32" />
        <path d="M16.5 26.69A9.15 9.15 0 0 1 16.5 41.31" />
        <path d="M88.5 26.69A9.15 9.15 0 0 0 88.5 41.31" />
        <path d="M0 1A1 1 0 0 0 1 0M104 0A1 1 0 0 0 105 1M105 67A1 1 0 0 0 104 68M1 68A1 1 0 0 0 0 67" />
      </g>
      <g fill="#fff" fillOpacity=".9">
        <circle cx="52.5" cy="34" r=".35" />
        <circle cx="11" cy="34" r=".3" />
        <circle cx="94" cy="34" r=".3" />
      </g>
      <rect x="-2" y="30.34" width="2" height="7.32" fill="url(#itgNet)" stroke="#fff" strokeWidth=".25" />
      <rect x="105" y="30.34" width="2" height="7.32" fill="url(#itgNet)" stroke="#fff" strokeWidth=".25" />
      <rect x="-3" y="-3" width="111" height="74" fill="url(#itgLamp)" />
    </svg>
  );
});

// Goalkeepers wear a fixed contrasting kit; outfield players the team colours from the match data.
const GK = { home: { bg: '#F06EB4', fg: '#121212', ring: '#FFFFFF' }, away: { bg: '#202020', fg: '#FFFFFF', ring: '#FFFFFF' } };
const chipColors = (p: Player, side: 'home' | 'away', team?: TeamInfo) => {
  if (p.gk) return GK[side];
  const bg = team?.color ?? '#888888';
  const fg = team?.fg ?? '#FFFFFF';
  return { bg, fg, ring: fg };
};

export function PlayerChips({ players, positions }: { players: Player[]; positions: Record<string, Point> }) {
  const teams = useTeams();
  return (
    <>
      {players.map((p) => {
        const pos = positions[p.id] ?? p;
        const c = chipColors(p, teams.side(p.team) ?? 'home', teams.info(p.team));
        return (
          <div
            key={p.id}
            className="absolute box-border flex h-[38px] w-[38px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full font-display text-[20px] font-extrabold leading-none shadow-[0_4px_8px_rgba(0,0,0,.45),0_1px_2px_rgba(0,0,0,.4)]"
            style={{ ...pct(pos), background: c.bg, color: c.fg, border: `2px solid ${c.ring}` }}
            title={p.name ? `${p.n} ${p.name}` : `${p.n}`}
          >
            {p.n}
          </div>
        );
      })}
    </>
  );
}

export function BallMarker({ at }: { at: Point }) {
  return (
    <div className="absolute h-[18px] w-[18px] -translate-x-1/2 -translate-y-1/2 drop-shadow-[0_3px_3px_rgba(0,0,0,.5)]" style={pct(at)}>
      <Ball />
    </div>
  );
}
