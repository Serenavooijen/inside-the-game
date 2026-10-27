'use client';

import { useEffect, useRef, useState } from 'react';
import {
  average, endAt, heatCells, minuteAt, minutesBetween, samples, statsAt, statusAt,
  type LineupPlayer, type Lineups, type PlayerStats,
} from '@/lib/lineups';
import { useTeams } from '@/lib/teams';
import { SmallBall } from './icons';
import { ArrowDown, AttackRow, CardIcon, Chip, HeatPitch, SectionLabel } from './Lineups';

type Props = {
  data: Lineups;
  player: LineupPlayer;
  t: number;
  /** the player is highlighted on the big pitch */
  shown: boolean;
  onShow: () => void;
  onBack: () => void;
  /** t = match second */
  onSeek: (t: number) => void;
};

const LAST = 15 * 60;

/** A stat tile: fixed height, so nothing shifts when a value changes; a changed value lifts the tile briefly. */
function Tile({ k, v, sub, muted }: { k: string; v: string; sub?: string; muted?: boolean }) {
  const prev = useRef(v);
  const [flash, setFlash] = useState(0);
  useEffect(() => {
    if (prev.current !== v) { prev.current = v; setFlash((n) => n + 1); }
  }, [v]);
  return (
    <div className="relative box-border flex h-[84px] min-w-0 flex-col justify-between overflow-hidden rounded-md border border-line bg-surface px-3 py-[10px]">
      {flash > 0 && <span key={flash} className="itg-flash pointer-events-none absolute inset-0 bg-surface-2" aria-hidden />}
      <div className="relative truncate font-mono text-label uppercase tracking-[.04em] text-fg-3">{k}</div>
      <div className={`relative whitespace-nowrap font-display text-[30px] font-extrabold leading-[.9] ${muted ? 'text-fg-3' : 'text-fg'}`}>{v}</div>
      <div className="relative min-h-[14px] whitespace-nowrap font-mono text-label text-fg-2">{sub}</div>
    </div>
  );
}

function tiles(s: PlayerStats | null) {
  if (!s) return ['Touches', 'Passes', 'Shots', 'Sprints', 'Distance', 'Top speed', 'Duels won', 'Recoveries'].map((k) => ({ k, v: '–', sub: '' }));
  return [
    { k: 'Touches', v: String(s.touches), sub: '' },
    { k: 'Passes', v: `${s.passes}/${s.attempts}`, sub: s.attempts ? `${Math.round((s.passes / s.attempts) * 100)}%` : '' },
    { k: 'Shots', v: String(s.shots), sub: `xG ${s.xg.toFixed(2)}` },
    { k: 'Sprints', v: String(s.sprints), sub: '' },
    { k: 'Distance', v: s.km.toFixed(1), sub: 'km' },
    { k: 'Top speed', v: s.top.toFixed(1), sub: 'km/h' },
    { k: 'Duels won', v: `${s.duelsWon}/${s.duels}`, sub: '' },
    { k: 'Recoveries', v: String(s.recoveries), sub: '' },
  ];
}

const goals = (p: LineupPlayer, t: number) => p.moments.filter(([s, , k]) => k === 'goal' && s <= t).length;
const range = (data: Lineups, a: number, b: number) => `${minuteAt(a, data.halftime)}–${minuteAt(b, data.halftime)}'`;

/** Two players of one substitution side by side: heatmaps and five numbers. */
function Comparison({ data, before, after, t, title }: { data: Lineups; before: LineupPlayer; after: LineupPlayer; t: number; title: string }) {
  const side = (p: LineupPlayer) => {
    const a = p.on![0], b = endAt(p, t);
    const pts = samples(data, p, a, b);
    return { p, a, b, pts, s: statsAt(data, p, t) };
  };
  const L = side(before), R = side(after);
  const rows: { k: string; a: string; as?: string; b: string; bs?: string }[] = [
    { k: 'Minutes', a: String(minutesBetween(L.a, L.b, data.halftime)), b: String(minutesBetween(R.a, R.b, data.halftime)) },
    { k: 'Touches', a: String(L.s?.touches ?? 0), b: String(R.s?.touches ?? 0) },
    { k: 'Shots', a: String(L.s?.shots ?? 0), as: `xG ${(L.s?.xg ?? 0).toFixed(2)}`, b: String(R.s?.shots ?? 0), bs: `xG ${(R.s?.xg ?? 0).toFixed(2)}` },
    { k: 'Goals', a: String(goals(before, t)), b: String(goals(after, t)) },
    { k: 'Sprints', a: String(L.s?.sprints ?? 0), b: String(R.s?.sprints ?? 0) },
  ];
  return (
    <div className="flex flex-col gap-3 border-t border-line pt-4">
      <SectionLabel>{title}</SectionLabel>
      <div className="grid grid-cols-2 gap-3">
        {[L, R].map((x) => (
          <div key={x.p.id} className="flex min-w-0 flex-col gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <Chip p={x.p} size={24} />
              <span className="truncate text-[14px] font-semibold">{x.p.name.split('. ').pop()}</span>
              <span className="ml-auto flex-none font-mono text-label text-fg-3">{range(data, x.a, x.b)}</span>
            </div>
            <HeatPitch team={x.p.team} cells={heatCells(x.pts)} avg={average(x.pts)} />
          </div>
        ))}
      </div>
      <div className="flex flex-col">
        {rows.map((r) => (
          <div key={r.k} className="grid h-[34px] grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 border-b border-line">
            <div className="font-display text-[22px] font-extrabold leading-none">{r.a}{r.as && <span className="font-mono text-[12px] font-normal text-fg-2"> {r.as}</span>}</div>
            <div className="text-center font-mono text-label uppercase tracking-[.08em] text-fg-3">{r.k}</div>
            <div className="text-right font-display text-[22px] font-extrabold leading-none">{r.b}{r.bs && <span className="font-mono text-[12px] font-normal text-fg-2"> {r.bs}</span>}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

const LABEL = { goal: 'Goal', assist: 'Assist', yellow: 'Yellow', red: 'Red', off: 'Off', on: 'On' } as const;

/** Player analysis in the right column: header, live numbers, heatmap, moments, substitution. */
export function PlayerPanel({ data, player: p, t, shown, onShow, onBack, onSeek }: Props) {
  const teams = useTeams();
  const [span, setSpan] = useState<'all' | 'last'>('all');
  useEffect(() => setSpan('all'), [p.id]);
  const st = statusAt(p, t);
  const bench = st === 'bench';
  const end = endAt(p, t);
  const start = p.on?.[0] ?? 0;
  const from = span === 'all' ? start : Math.max(start, end - LAST);
  const pts = bench ? [] : samples(data, p, from, end);
  const stats = statsAt(data, p, t);
  const at = (s: number) => Math.min(100, (s / data.duration) * 100);
  const moments = p.moments.filter(([s, , k]) => s <= t && k !== 'on');
  const canShow = st === 'on';
  const byId = (id?: string | null) => data.players.find((x) => x.id === id);
  const by = p.off?.reason === 'sub' && p.off.t <= t ? byId(p.off.by) : undefined;
  const replaced = p.replaced && !bench ? byId(p.replaced) : undefined;

  const toggle = (k: 'all' | 'last', label: string) => (
    <button
      type="button"
      onClick={() => setSpan(k)}
      aria-pressed={span === k}
      className={`h-7 whitespace-nowrap rounded-sm px-[10px] text-[13px] font-semibold ${span === k ? 'bg-fg text-bg' : 'bg-transparent text-fg-2 hover:text-fg'}`}
    >
      {label}
    </button>
  );

  return (
    <div className="flex w-full flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={onBack}
          className="flex h-9 items-center gap-[6px] rounded-full border border-line bg-transparent pl-[10px] pr-[14px] text-[14px] font-semibold text-fg hover:bg-surface-2"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
          Back
        </button>
        <button
          type="button"
          onClick={canShow ? onShow : undefined}
          disabled={!canShow}
          aria-pressed={canShow && shown}
          className={`flex h-9 items-center gap-2 whitespace-nowrap rounded-full border pl-3 pr-[14px] text-[14px] font-semibold ${canShow && shown ? 'border-fg bg-fg text-bg' : 'border-line-strong bg-transparent text-fg'} ${canShow ? 'cursor-pointer' : 'cursor-not-allowed opacity-[.45]'}`}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="3" /></svg>
          {!canShow ? 'Not on the pitch' : shown ? 'Shown on pitch' : 'Show on pitch'}
        </button>
      </div>

      <div className="flex min-w-0 items-center gap-[14px]">
        <Chip p={p} size={52} dim={st === 'red' ? 0.45 : bench ? 0.6 : undefined} className="shadow-[0_4px_8px_rgba(0,0,0,.35)]" />
        <div className="flex min-w-0 flex-col gap-[6px]">
          <h2 className="truncate font-display text-[34px] font-extrabold uppercase leading-[.9]">{p.name}</h2>
          <div className="flex flex-wrap items-center gap-2 text-[14px] text-fg-2">
            <span className="inline-block h-[10px] w-[10px] rounded-[3px]" style={{ background: teams.color(p.team) }} />
            {teams.label(p.team)} · {p.roleName}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {st === 'on' && (
          <span className="flex h-[30px] items-center gap-2 rounded-full bg-surface-2 px-3 text-[14px] font-semibold">
            <span className="h-2 w-2 rounded-full bg-corrected" />On the pitch
          </span>
        )}
        {st === 'off' && (
          <span className="flex h-[30px] items-center gap-[6px] rounded-full bg-surface-2 pl-[10px] pr-3 text-[14px] font-semibold">
            <ArrowDown size={14} />Subbed off {p.off!.minute}&apos;
          </span>
        )}
        {st === 'red' && (
          <span className="flex h-[30px] items-center gap-2 rounded-full bg-corrected-soft pl-[10px] pr-3 text-[14px] font-semibold text-corrected">
            <CardIcon red w={10} h={14} />Sent off {p.off!.minute}&apos;
          </span>
        )}
        {bench && (
          <span className="flex h-[30px] items-center rounded-full bg-surface-2 px-3 text-[14px] font-semibold text-fg-2">On the bench · not played yet</span>
        )}
        {(st === 'off' || st === 'red') && (
          <span className="flex h-[30px] items-center rounded-full border border-line-strong px-3 font-mono text-[12px] uppercase tracking-[.12em]">Final</span>
        )}
        <span className="ml-auto flex items-baseline gap-[6px]">
          <span className="font-display text-[30px] font-extrabold leading-none">{bench ? 0 : minutesBetween(start, end, data.halftime)}&apos;</span>
          <span className="font-mono text-label uppercase tracking-[.08em] text-fg-3">played</span>
        </span>
      </div>

      <div className="flex flex-col gap-[10px]">
        <div className="flex items-center justify-between gap-3">
          <SectionLabel>Key numbers</SectionLabel>
          <SectionLabel className="text-right">
            {st === 'on' ? 'Live · updates every 10 s' : bench ? 'Starts when he comes on' : `Frozen at ${p.off!.minute}'`}
          </SectionLabel>
        </div>
        <div className="grid grid-cols-4 gap-2">
          {tiles(stats).map((x) => <Tile key={x.k} k={x.k} v={x.v} sub={x.sub} muted={bench} />)}
        </div>
      </div>

      <div className="flex flex-col gap-[10px]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SectionLabel>Heatmap · {bench ? 'no data' : range(data, from, end)}</SectionLabel>
          {!bench && (
            <div className="flex gap-[2px] rounded-md bg-surface-2 p-[3px]" role="group" aria-label="Heatmap period">
              {toggle('all', 'Whole match')}
              {toggle('last', 'Last 15 min')}
            </div>
          )}
        </div>
        <HeatPitch team={p.team} cells={heatCells(pts)} avg={average(pts)} empty={bench ? 'No data yet. The heatmap starts when he comes on.' : undefined} />
        {!bench && (
          <>
            <AttackRow note="Both halves shown left to right" />
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px] text-fg-2">
              <span className="flex items-center gap-2"><span className="h-[10px] w-[10px] rounded-full bg-fg" />Average position</span>
              <span className="flex items-center gap-[6px]">
                Less
                <span className="flex gap-[2px]">
                  {[0.14, 0.3, 0.5, 0.7, 0.9].map((o) => <span key={o} className="h-[10px] w-[14px] rounded-[2px]" style={{ background: teams.color(p.team), opacity: o }} />)}
                </span>
                More
              </span>
            </div>
          </>
        )}
      </div>

      <div className="flex flex-col gap-[10px]">
        <SectionLabel>Moments</SectionLabel>
        <div className="relative h-16">
          <div className="absolute left-0 right-0 top-[30px] h-[6px] rounded-full bg-surface-2">
            {!bench && <div className="absolute bottom-0 top-0 rounded-full bg-fg-3" style={{ left: `${at(start)}%`, width: `${at(end) - at(start)}%` }} />}
            <div className="absolute top-[-3px] h-3 w-[2px] bg-line-strong" style={{ left: `${at(data.halftime)}%` }} />
          </div>
          {moments.map(([s, minute, k]) => (
            <button
              key={`${k}-${s}`}
              type="button"
              onClick={() => onSeek(Math.max(0, s - 8))}
              title={`Jump to ${minute}'`}
              className={`absolute top-0 flex flex-col gap-[10px] bg-transparent p-0 text-fg ${at(s) > 88 ? '-translate-x-full items-end' : at(s) < 8 ? 'items-start' : '-translate-x-1/2 items-center'}`}
              style={{ left: `${at(s)}%` }}
            >
              <span className="flex h-5 items-center">
                {k === 'goal' && <SmallBall />}
                {k === 'assist' && <span className="box-border flex h-4 w-4 items-center justify-center rounded-full border-2 border-fg font-display text-[10px] font-extrabold">A</span>}
                {k === 'yellow' && <CardIcon w={11} h={15} />}
                {k === 'red' && <CardIcon red w={11} h={15} />}
                {k === 'off' && <ArrowDown size={16} />}
              </span>
              <span className="whitespace-nowrap pt-[6px] font-mono text-[12px] text-fg-2">{minute}&apos; {LABEL[k]}</span>
            </button>
          ))}
          {bench && <div className="absolute left-0 top-11 text-[13px] text-fg-3">No minutes yet</div>}
        </div>
      </div>

      {by && <Comparison data={data} before={p} after={by} t={t} title={`Replaced by · ${p.off!.minute}'`} />}
      {replaced && <Comparison data={data} before={replaced} after={p} t={t} title={`Replaced · ${replaced.off!.minute}'`} />}
      {st === 'red' && (
        <div className="flex flex-col gap-[6px] border-t border-line pt-4">
          <SectionLabel>Substitution</SectionLabel>
          <div className="text-[15px] text-fg-2">No replacement. {teams.label(p.team)} played with 10 men from {p.off!.minute}&apos;.</div>
        </div>
      )}
    </div>
  );
}
