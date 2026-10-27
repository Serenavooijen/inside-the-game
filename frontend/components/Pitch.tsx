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
export const chipColors = (p: { gk?: boolean }, side: 'home' | 'away', team?: TeamInfo) => {
  if (p.gk) return GK[side];
  const bg = team?.color ?? '#888888';
  const fg = team?.fg ?? '#FFFFFF';
  return { bg, fg, ring: fg };
};

type ChipProps = {
  players: Player[];
  positions: Record<string, Point>;
  /** player under the pointer: 2 px ring at 70% */
  hoverId?: string | null;
  /** player shown on the pitch: 3 px ring in fg */
  selectedId?: string | null;
  onHover?: (id: string | null) => void;
  onPick?: (id: string) => void;
};

export function PlayerChips({ players, positions, hoverId, selectedId, onHover, onPick }: ChipProps) {
  const teams = useTeams();
  return (
    <>
      {players.map((p) => {
        const pos = positions[p.id] ?? p;
        const c = chipColors(p, teams.side(p.team) ?? 'home', teams.info(p.team));
        const sel = selectedId === p.id;
        const hov = hoverId === p.id;
        const Tag = onPick ? 'button' : 'div';
        return (
          <Tag
            key={p.id}
            type={onPick ? 'button' : undefined}
            onClick={onPick ? () => onPick(p.id) : undefined}
            onPointerEnter={onHover ? () => onHover(p.id) : undefined}
            onPointerLeave={onHover ? () => onHover(null) : undefined}
            onFocus={onHover ? () => onHover(p.id) : undefined}
            onBlur={onHover ? () => onHover(null) : undefined}
            aria-label={onPick ? `${p.n} ${p.name ?? ''}, open player analysis` : undefined}
            className={`absolute box-border flex h-[38px] w-[38px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full p-0 font-display text-[20px] font-extrabold leading-none shadow-[0_4px_8px_rgba(0,0,0,.45),0_1px_2px_rgba(0,0,0,.4)] ${onPick ? 'cursor-pointer focus-visible:outline-none' : ''}`}
            style={{
              ...pct(pos), background: c.bg, color: c.fg, border: `2px solid ${c.ring}`,
              outline: sel ? '3px solid var(--itg-fg)' : hov ? '2px solid rgba(244,242,238,.7)' : 'none', outlineOffset: 3,
              zIndex: sel || hov ? 2 : undefined,
            }}
            title={onPick ? undefined : p.name ? `${p.n} ${p.name}` : `${p.n}`}
          >
            {p.n}
          </Tag>
        );
      })}
    </>
  );
}

/** Hover tooltip next to a chip on the big pitch. */
export function ChipTooltip({ player, at }: { player: Player; at: Point }) {
  const flip = at.x > 78;
  return (
    <div
      className="pointer-events-none absolute z-[3] flex items-center gap-3 whitespace-nowrap rounded-md border border-white/[.14] bg-[rgba(12,14,13,.92)] py-2 pl-[10px] pr-3 text-chalk shadow-[0_12px_32px_rgba(0,0,0,.35)]"
      style={{ left: `calc(${pct(at).left} ${flip ? '-' : '+'} 30px)`, top: pct(at).top, transform: `translate(${flip ? '-100%' : '0'}, -50%)` }}
      role="tooltip"
    >
      <div className="flex flex-col gap-[2px]">
        <div className="font-display text-[18px] font-bold uppercase leading-none tracking-[.04em]">{player.n} · {player.name ?? ''}</div>
        <div className="text-[13px] text-[#B8B4AD]">Click to open player analysis</div>
      </div>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#F4F2EE" strokeWidth="2" strokeLinecap="round" aria-hidden><path d="m9 6 6 6-6 6" /></svg>
    </div>
  );
}

/** The TV name label (shirt number in the team colour + name in caps). */
export function NameTag({ player, booked }: { player: Player; booked?: boolean }) {
  const teams = useTeams();
  const info = teams.info(player.team);
  return (
    <div className="flex h-[34px] w-max overflow-hidden whitespace-nowrap rounded-sm shadow-[0_4px_12px_rgba(0,0,0,.35)]">
      <div className="flex w-[34px] items-center justify-center font-display text-[20px] font-extrabold" style={{ background: info?.color, color: info?.fg }}>{player.n}</div>
      <div className="flex items-center gap-2 bg-[rgba(12,14,13,.9)] px-3 font-display text-[20px] font-bold uppercase tracking-[.04em] text-chalk">
        {player.name ?? `No. ${player.n}`}
        {booked && <span className="inline-block h-[14px] w-[10px] rounded-[2px] bg-card-yellow" aria-label="booked" />}
      </div>
    </div>
  );
}

/** Show on pitch: the name label under the selected chip. */
export function SelectedTag({ player, at }: { player: Player; at: Point }) {
  return (
    <div className="itg-in pointer-events-none absolute z-[3] -translate-x-1/2" style={{ left: pct(at).left, top: `calc(${pct(at).top} + 32px)` }}>
      <NameTag player={player} />
    </div>
  );
}

export function BallMarker({ at }: { at: Point }) {
  return (
    <div className="absolute h-[18px] w-[18px] -translate-x-1/2 -translate-y-1/2 drop-shadow-[0_3px_3px_rgba(0,0,0,.5)]" style={pct(at)}>
      <Ball />
    </div>
  );
}
