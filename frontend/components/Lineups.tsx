'use client';

import { useState, type ReactNode } from 'react';
import type { TeamId } from '@/lib/contracts';
import {
  HEAT_COLS, HEAT_ROWS, average, endAt, formationAt, formationBoth, lineHeight, minuteAt, samples, statusAt,
  type LineupPlayer, type Lineups,
} from '@/lib/lineups';
import { useLang } from '@/lib/i18n';
import { useTeams } from '@/lib/teams';
import { chipColors } from './Pitch';
import { SmallBall } from './icons';
import { CornerSummary } from './Corners';

const pctX = (x: number) => `${((x + 3) / 111) * 100}%`;
const pctY = (y: number) => `${((y + 3) / 74) * 100}%`;
const STRIPES = [4.93, 20.79, 36.64, 52.5, 68.36, 84.21, 100.07];

// Starting XI from the back to the front, as on a team sheet.
const ROLE_ORDER = ['GK', 'RB', 'CB', 'LB', 'DM', 'CM', 'AM', 'RM', 'LM', 'RW', 'LW', 'ST'];
const byRole = (a: LineupPlayer, b: LineupPlayer) => ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role) || a.n - b.n;

/** Kit colours for a player of the match (goalkeepers in their own kit). */
export function useKit() {
  const teams = useTeams();
  return (p: { team: TeamId; gk?: boolean }) => chipColors(p, teams.side(p.team) ?? 'home', teams.info(p.team));
}

/** Shirt number in the kit colours. */
export function Chip({ p, size, dim, className = '' }: { p: { team: TeamId; n: number; gk?: boolean }; size: number; dim?: number; className?: string }) {
  const kit = useKit()(p);
  return (
    <span
      className={`box-border flex flex-none items-center justify-center rounded-full font-display font-extrabold leading-none ${className}`}
      style={{
        width: size, height: size, fontSize: Math.round(size * 0.54), background: kit.bg, color: kit.fg,
        border: `${size >= 40 ? 2 : 1.5}px solid ${kit.ring}`, opacity: dim,
      }}
      aria-hidden
    >
      {p.n}
    </span>
  );
}

function PitchLines({ stroke, opacity, width }: { stroke: string; opacity: number; width: number }) {
  return (
    <g fill="none" stroke={stroke} strokeOpacity={opacity} strokeWidth={width}>
      <rect x="0" y="0" width="105" height="68" />
      <line x1="52.5" y1="0" x2="52.5" y2="68" />
      <circle cx="52.5" cy="34" r="9.15" />
      <rect x="0" y="13.84" width="16.5" height="40.32" />
      <rect x="88.5" y="13.84" width="16.5" height="40.32" />
      <rect x="0" y="24.84" width="5.5" height="18.32" />
      <rect x="99.5" y="24.84" width="5.5" height="18.32" />
    </g>
  );
}

export type PitchChip = { id: string; team: TeamId; n: number; gk?: boolean; name: string; x: number; y: number; dim?: boolean };

/** Mini pitch on grass with the average positions as chips. */
export function GrassPitch({ chips, size = 24, highlightId, onPick }: { chips: PitchChip[]; size?: number; highlightId?: string | null; onPick?: (id: string) => void }) {
  const kit = useKit();
  const { t } = useLang();
  return (
    <div className="relative w-full overflow-hidden rounded-md" style={{ aspectRatio: '111 / 74' }}>
      <svg viewBox="-3 -3 111 74" className="absolute inset-0 block h-full w-full" aria-hidden>
        <rect x="-3" y="-3" width="111" height="74" fill="var(--itg-grass-a)" />
        <g fill="var(--itg-grass-b)">{STRIPES.map((x) => <rect key={x} x={x} y="-3" width="7.93" height="74" />)}</g>
        <PitchLines stroke="#fff" opacity={0.8} width={0.45} />
      </svg>
      {chips.map((c) => {
        const k = kit(c);
        return (
          <button
            key={c.id}
            type="button"
            onClick={onPick ? () => onPick(c.id) : undefined}
            title={c.name}
            aria-label={`${c.n} ${c.name}, ${t('openPlayer')}`}
            className="absolute box-border flex -translate-x-1/2 -translate-y-1/2 cursor-pointer items-center justify-center rounded-full p-0 font-display font-extrabold leading-none shadow-[0_2px_4px_rgba(0,0,0,.4)] [outline-offset:2px] hover:outline hover:outline-2 hover:outline-[#F4F2EE]"
            style={{
              left: pctX(c.x), top: pctY(c.y), width: size, height: size, fontSize: Math.round(size * 0.56),
              background: k.bg, color: k.fg, border: `1.5px solid ${k.ring}`, opacity: c.dim ? 0.4 : 1,
              outline: highlightId === c.id ? '2px solid var(--itg-fg)' : undefined,
            }}
          >
            {c.n}
          </button>
        );
      })}
    </div>
  );
}

/** Heatmap on a dark mini pitch: 21 × 14 cells in the team colour, average position as a dot. */
export function HeatPitch({ team, cells, avg, empty }: { team: TeamId; cells: number[]; avg?: { x: number; y: number } | null; empty?: string }) {
  const teams = useTeams();
  const { t } = useLang();
  return (
    <div className="relative w-full overflow-hidden rounded-md bg-surface-2" style={{ aspectRatio: '111 / 74' }}>
      {cells.length > 0 && (
        <div
          className="absolute grid"
          style={{ left: '2.7%', top: '4.05%', width: '94.6%', height: '91.9%', gridTemplateColumns: `repeat(${HEAT_COLS}, minmax(0, 1fr))`, gridTemplateRows: `repeat(${HEAT_ROWS}, minmax(0, 1fr))` }}
          aria-hidden
        >
          {cells.map((o, k) => <div key={k} style={{ background: teams.color(team), opacity: o }} />)}
        </div>
      )}
      <svg viewBox="-3 -3 111 74" className="absolute inset-0 block h-full w-full" aria-hidden>
        <PitchLines stroke="var(--itg-fg-3)" opacity={0.7} width={0.45} />
      </svg>
      {avg && (
        <div
          className="absolute h-[14px] w-[14px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-fg shadow-[0_0_0_3px_var(--itg-surface-2)]"
          style={{ left: pctX(avg.x), top: pctY(avg.y) }}
          aria-label={t('averagePosition')}
        />
      )}
      {empty && <div className="absolute inset-0 flex items-center justify-center p-6 text-center text-[14px] text-fg-2">{empty}</div>}
    </div>
  );
}

/** "Attacking →" under every team-relative pitch. */
export function AttackRow({ note }: { note: string }) {
  const { t } = useLang();
  return (
    <div className="flex flex-wrap items-center gap-x-[10px] gap-y-1 font-mono text-label text-fg-3">
      <span className="uppercase tracking-[.08em]">{t('attacking')}</span>
      <svg width="56" height="10" viewBox="0 0 56 10" fill="none" stroke="var(--itg-fg-2)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-label="left to right"><path d="M1 5h53M49 1l5 4-5 4" /></svg>
      <span>{note}</span>
    </div>
  );
}

export const SectionLabel = ({ children, className = '' }: { children: ReactNode; className?: string }) => (
  <div className={`font-mono text-label uppercase tracking-[.12em] text-fg-3 ${className}`}>{children}</div>
);

export const ArrowUp = ({ size = 12 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="var(--itg-ok)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-label="subbed on"><path d="M12 20V4M5 11l7-7 7 7" /></svg>
);
export const ArrowDown = ({ size = 12 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="var(--itg-bad)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-label="subbed off"><path d="M12 4v16M5 13l7 7 7-7" /></svg>
);
export const CardIcon = ({ red, w = 9, h = 12 }: { red?: boolean; w?: number; h?: number }) => (
  <span className={`inline-block flex-none rounded-[2px] ${red ? 'bg-card-red' : 'bg-card-yellow'}`} style={{ width: w, height: h }} aria-label={red ? 'red card' : 'yellow card'} />
);

/** Status icons of a line-up row: what has happened up to now, with the minute. */
function RowEvents({ p, t }: { p: LineupPlayer; t: number }) {
  const ms = p.moments.filter(([s, , k]) => s <= t && k !== 'assist');
  return (
    <div className="flex flex-wrap items-center justify-end gap-x-[10px] gap-y-1">
      {ms.map(([s, minute, k]) => (
        <span key={`${k}-${s}`} className="flex items-center gap-1 font-mono text-[12px] text-fg-2">
          {k === 'goal' && <SmallBall />}
          {k === 'yellow' && <CardIcon />}
          {k === 'red' && <CardIcon red />}
          {k === 'on' && <ArrowUp />}
          {k === 'off' && <ArrowDown />}
          {minute}&apos;
        </span>
      ))}
    </div>
  );
}

function Row({ p, t, highlight, onPick }: { p: LineupPlayer; t: number; highlight: boolean; onPick: (id: string) => void }) {
  const { t: tr } = useLang();
  const st = statusAt(p, t);
  const bench = !p.starter && st === 'bench';
  return (
    <button
      type="button"
      onClick={() => onPick(p.id)}
      className={`grid h-10 w-full grid-cols-[28px_minmax(0,1fr)_auto_16px] items-center gap-3 rounded-sm border-b border-line px-2 text-left hover:bg-surface-2 ${highlight ? 'bg-surface-2' : 'bg-transparent'}`}
      style={{ opacity: st === 'red' ? 0.45 : 1 }}
    >
      <Chip p={p} size={26} dim={bench ? 0.6 : undefined} />
      <span className="flex min-w-0 items-baseline gap-[10px]">
        <span className={`truncate text-[15px] font-semibold ${bench ? 'text-fg-2' : 'text-fg'}`}>{p.name}</span>
        <span className="flex-none font-mono text-[12px] text-fg-3">{p.role}</span>
      </span>
      {bench ? <span className="font-mono text-[12px] text-fg-3">{tr('onTheBench')}</span> : <RowEvents p={p} t={t} />}
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--itg-fg-3)" strokeWidth="2" strokeLinecap="round" aria-hidden><path d="m9 6 6 6-6 6" /></svg>
    </button>
  );
}

type Props = {
  data: Lineups;
  t: number;
  mode: 'casual' | 'analyst';
  team: TeamId;
  onTeam: (team: TeamId) => void;
  /** row that lights up (hover on the big pitch) */
  highlightId?: string | null;
  onPick: (playerId: string) => void;
};

/** Line-ups tab: the current shape of both teams (TV line-up) or the average positions of one team; the team sheet of one team. */
export function LineupsPanel({ data, t, mode, team, onTeam, highlightId, onPick }: Props) {
  const teams = useTeams();
  const { t: tr } = useLang();
  const [view, setView] = useState<'formation' | 'average'>('formation');
  const other = team === teams.home.id ? teams.away.id : teams.home.id;
  const squad = data.players.filter((p) => p.team === team);
  const starters = squad.filter((p) => p.starter).sort(byRole);
  const played = (p: LineupPlayer) => !!p.on && p.on[0] <= t;
  const subs = squad.filter((p) => !p.starter).sort((a, b) => Number(played(b)) - Number(played(a)) || (a.on?.[0] ?? 1e9) - (b.on?.[0] ?? 1e9) || byRole(a, b));

  // Formation: both teams as a TV line-up, home on the left half, away on the right half; a substitute in the
  // place of the player he replaced. Average positions: one team, who is on the pitch now, where they stood on
  // average; a sent-off player stays, dimmed.
  const byId = Object.fromEntries(data.players.map((p) => [p.id, p]));
  const chips: PitchChip[] = view === 'formation'
    ? formationBoth(data, teams.home.id, teams.away.id, t).map(({ id, team: tm, x, y }) => ({ id, team: tm, n: byId[id].n, gk: byId[id].gk, name: byId[id].name, x, y }))
    : squad.flatMap((p) => {
      const st = statusAt(p, t);
      if (st !== 'on' && st !== 'red') return [];
      const a = average(samples(data, p, p.on![0], endAt(p, t)));
      return a ? [{ id: p.id, team: p.team, n: p.n, gk: p.gk, name: p.name, x: a.x, y: a.y, dim: st === 'red' }] : [];
    });
  const height = view === 'average' ? lineHeight(data, team, t) : null;

  const viewBtn = (v: 'formation' | 'average', label: string) => (
    <button
      type="button"
      onClick={() => setView(v)}
      aria-pressed={view === v}
      className={`h-7 whitespace-nowrap rounded-sm px-[10px] text-[13px] font-semibold ${view === v ? 'bg-fg text-bg' : 'bg-transparent text-fg-2 hover:text-fg'}`}
    >
      {label}
    </button>
  );

  const seg = (id: TeamId) => (
    <button
      key={id}
      type="button"
      onClick={() => onTeam(id)}
      aria-pressed={team === id}
      className={`flex h-10 min-w-0 items-center justify-center gap-2 rounded-sm text-[15px] font-semibold ${team === id ? 'bg-fg text-bg' : 'bg-transparent text-fg-2 hover:text-fg'}`}
    >
      <span className="inline-block h-[10px] w-[10px] flex-none rounded-[3px]" style={{ background: teams.color(id) }} />
      <span className="truncate">{teams.label(id)}</span>
    </button>
  );

  // In Formation the switch only picks the team sheet under the pitch; in Average positions also the pitch.
  const teamSwitch = (
    <div className="grid grid-cols-2 gap-[2px] rounded-md bg-surface-2 p-[3px]" role="group" aria-label={tr('team')}>
      {seg(teams.home.id)}
      {seg(teams.away.id)}
    </div>
  );

  return (
    <div className="flex w-full flex-col gap-4">
      {mode === 'analyst' && <CornerSummary corners={data.corners.filter((c) => c.t <= t)} cup={data.cup} players={data.players} range={`0–${minuteAt(t, data.halftime)}'`} />}

      {view === 'average' && teamSwitch}

      <div className="flex flex-wrap items-end justify-between gap-x-3 gap-y-1">
        {view === 'formation' ? (
          <div className="flex items-baseline gap-[10px] font-display text-[44px] font-extrabold leading-[.85]" aria-label={tr('formation')}>
            <span className="flex items-baseline gap-2" style={{ color: teams.text(teams.home.id) }}>
              <span className="font-mono text-[13px] font-medium">{teams.short(teams.home.id)}</span>{formationAt(data, teams.home.id, t)}
            </span>
            <span className="text-[28px] text-fg-3">·</span>
            <span className="flex items-baseline gap-2" style={{ color: teams.text(teams.away.id) }}>
              {formationAt(data, teams.away.id, t)}<span className="font-mono text-[13px] font-medium">{teams.short(teams.away.id)}</span>
            </span>
          </div>
        ) : (
          <div className="flex items-baseline gap-[10px]">
            <span className="font-display text-[44px] font-extrabold leading-[.85]">{formationAt(data, team, t)}</span>
            <span className="text-[14px] text-fg-2">{tr('vs')} {formationAt(data, other, t)} {teams.label(other)}</span>
          </div>
        )}
        <div className="flex gap-[2px] rounded-md bg-surface-2 p-[3px]" role="group" aria-label={tr('pitchView')}>
          {viewBtn('formation', tr('formation'))}
          {viewBtn('average', tr('averagePositions'))}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <GrassPitch chips={chips} highlightId={highlightId} onPick={onPick} />
        {view === 'formation' ? (
          <div className="flex flex-wrap items-center gap-x-[10px] gap-y-1 font-mono text-label text-fg-3">
            <span className="uppercase tracking-[.08em]" style={{ color: teams.text(teams.home.id) }}>{teams.short(teams.home.id)} →</span>
            <span className="uppercase tracking-[.08em]" style={{ color: teams.text(teams.away.id) }}>← {teams.short(teams.away.id)}</span>
            <span>{tr('shapeAt', { m: minuteAt(t, data.halftime) })}</span>
          </div>
        ) : (
          <>
            <AttackRow note={tr('avgNote', { m: minuteAt(t, data.halftime) }) + (chips.some((c) => c.dim) ? ` · ${tr('dimmedSentOff')}` : '')} />
            {height !== null && <div className="font-mono text-label uppercase tracking-[.08em] text-fg-2">{tr('lineHeight', { h: height })}</div>}
          </>
        )}
      </div>

      {view === 'formation' && teamSwitch}

      <div className="flex flex-col">
        <SectionLabel className="pb-[6px]">{tr('startingXI')}</SectionLabel>
        {starters.map((p) => <Row key={p.id} p={p} t={t} highlight={highlightId === p.id} onPick={onPick} />)}
        <SectionLabel className="pb-[6px] pt-[18px]">{tr('substitutes')}</SectionLabel>
        {subs.map((p) => <Row key={p.id} p={p} t={t} highlight={highlightId === p.id} onPick={onPick} />)}
      </div>
    </div>
  );
}
