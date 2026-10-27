'use client';

import type { TeamId } from '@/lib/contracts';
import { cornerOutcome, useLang, type Key } from '@/lib/i18n';
import { type Corner, type CornerPlayer, type LineupPlayer, type Lineups } from '@/lib/lineups';
import { useTeams } from '@/lib/teams';
import { Chip, useKit } from './Lineups';

export function CornerFlag({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M7 22V2l10 5-10 5" /><path d="M3 22a4 4 0 0 1 8 0" />
    </svg>
  );
}

const FlagBox = () => (
  <div className="flex h-8 w-8 flex-none items-center justify-center rounded-md bg-surface-2 text-fg"><CornerFlag /></div>
);

// The box zoomed in: viewBox -3 -3 74 27, u 0–68 along the goal line, v = distance from it.
const pos = (u: number, v: number) => ({ left: `${((u + 3) / 74) * 100}%`, top: `${((v + 3) / 27) * 100}%` });
const VIEW_V = 23.5;

function OutcomeIcon({ kind }: { kind: Corner['outcome']['kind'] }) {
  const goal = kind === 'goal';
  return (
    <div className={`flex h-7 w-7 flex-none items-center justify-center rounded-full ${goal ? 'bg-fg text-bg' : 'bg-surface-2 text-fg'}`} aria-hidden>
      {goal && <svg width="16" height="16" viewBox="0 0 12 12"><circle cx="6" cy="6" r="5" fill="#fff" stroke="#121212" /><path d="M6 3.5 8.3 5.2 7.4 8H4.6L3.7 5.2Z" fill="#121212" /></svg>}
      {kind === 'header' && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="7" r="4" /><path d="M5 21a7 7 0 0 1 14 0" /></svg>}
      {kind === 'shot' && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4" /></svg>}
      {kind === 'cleared' && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" /></svg>}
      {kind === 'short' && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>}
    </div>
  );
}

/** Corner in the feed. Made by code from the event data, no AI: who stood where at the delivery,
 *  who touched the ball first and what happened. Stored as a corner from the left; mirrored when drawn. */
export function CornerCard({ corner: c }: { corner: Corner }) {
  const teams = useTeams();
  const kit = useKit();
  const { t, lang, ordinal } = useLang();
  const R = c.side === 'right';
  const U = (u: number) => (R ? 68 - u : u);
  const opp: TeamId = c.team === teams.home.id ? teams.away.id : teams.home.id;
  const ft = c.firstTouch;
  const tu = U(Math.max(-2, Math.min(70, ft.u)));
  const tv = Math.min(VIEW_V, ft.v);
  const fu = U(-1.3);
  const short = c.outcome.kind === 'short';
  const ball = `M${fu} -1.2 Q${(fu + tu) / 2} ${short ? (tv - 1.2) / 2 : -5} ${tu} ${tv}`;
  const zones: { k: Key; u: number; v: number; left?: boolean }[] = [
    { k: 'nearPost', u: 22, v: -1.6 }, { k: 'farPost', u: 46, v: -1.6 },
    { k: 'penaltySpot', u: 35, v: 11, left: true }, { k: 'edgeOfBox', u: 34, v: 22.6 }, { k: 'short', u: 1.5, v: 15, left: true },
  ];
  const chip = (p: CornerPlayer, team: TeamId) => {
    const k = kit({ team, gk: p.gk });
    const touch = ft.id === p.id;
    return (
      <div
        key={p.id}
        className="absolute box-border flex h-5 w-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full font-display text-[12px] font-extrabold leading-none shadow-[0_2px_4px_rgba(0,0,0,.4)]"
        style={{ ...pos(U(p.u), p.v), background: k.bg, color: k.fg, border: `1.5px solid ${k.ring}`, outline: touch ? '2px solid #F4F2EE' : 'none', outlineOffset: 1, zIndex: touch ? 1 : undefined }}
      >
        {p.n}
      </div>
    );
  };
  const heights = [...c.attackers, ...c.defenders].filter((p) => p.height && p.v <= 16.5);

  return (
    <article className="box-border flex w-full flex-col gap-3 rounded-lg border border-line bg-surface px-[18px] py-4" aria-label={`${t('corner')} ${teams.short(c.team)} ${c.minute}'`}>
      <header className="flex items-center gap-[10px]">
        <FlagBox />
        <div className="font-display text-card-type font-extrabold uppercase leading-none tracking-[.05em]">{t('corner')}</div>
        <div className="flex items-center gap-[6px] font-mono text-[13px] text-fg-2">
          <span className="inline-block h-3 w-3 rounded-[3px]" style={{ background: teams.color(c.team) }} />
          {teams.short(c.team)}
        </div>
        <div className="ml-auto font-display text-[28px] font-extrabold leading-none">{c.minute}&apos;</div>
      </header>

      <div className="flex flex-wrap items-center gap-2 text-[14px] text-fg-2">
        <span>{t('cornerFor', { nth: ordinal(c.nth), team: teams.short(c.team) })}</span>
        <span className="flex h-[22px] items-center rounded-sm border border-line-strong px-2 font-mono text-[11px] uppercase tracking-[.08em] text-fg">{t(c.side === 'left' ? 'fromLeft' : 'fromRight')}</span>
        <span className="ml-auto font-mono text-label uppercase tracking-[.12em] text-fg-3">{t('eventData')}</span>
      </div>

      <div className="relative w-full overflow-hidden rounded-md" style={{ aspectRatio: '74 / 27', background: 'var(--itg-grass-a)' }}>
        <svg viewBox="-3 -3 74 27" className="absolute inset-0 block h-full w-full" aria-hidden>
          <g fill="var(--itg-grass-b)"><rect x="-3" y="2" width="74" height="4" /><rect x="-3" y="10" width="74" height="4" /><rect x="-3" y="18" width="74" height="4" /></g>
          <g fill="none" stroke="#fff" strokeOpacity=".8" strokeWidth=".22">
            <line x1="-3" y1="0" x2="71" y2="0" />
            <line x1="0" y1="0" x2="0" y2="24" /><line x1="68" y1="0" x2="68" y2="24" />
            <rect x="13.84" y="0" width="40.32" height="16.5" />
            <rect x="24.84" y="0" width="18.32" height="5.5" />
            <path d="M26.69 16.5A9.15 9.15 0 0 0 41.31 16.5" />
            <path d="M1 0A1 1 0 0 1 0 1M67 0A1 1 0 0 0 68 1" />
          </g>
          <rect x="30.34" y="-1.8" width="7.32" height="1.8" fill="#fff" fillOpacity=".18" stroke="#fff" strokeWidth=".22" />
          <circle cx="34" cy="11" r=".3" fill="#fff" />
          <path d={ball} fill="none" stroke="#fff" strokeWidth=".32" strokeDasharray=".9 .6" strokeLinecap="round" />
          <circle cx={tu} cy={tv} r="2.5" fill="none" stroke="#fff" strokeWidth=".25" />
        </svg>
        {zones.map((z) => (
          <div
            key={z.k}
            className="pointer-events-none absolute whitespace-nowrap font-mono text-[9px] uppercase tracking-[.1em] text-white/70"
            style={{ ...pos(U(z.u), z.v), transform: z.left ? (R ? 'translate(-100%,-50%)' : 'translate(0,-50%)') : 'translate(-50%,-50%)' }}
          >
            {t(z.k)}
          </div>
        ))}
        {c.defenders.map((p) => chip(p, opp))}
        {c.attackers.map((p) => chip(p, c.team))}
        {chip({ n: c.taker, u: -1.3, v: -1.2, id: c.takerId }, c.team)}
        {heights.map((p) => (
          <div key={`h-${p.id}`} className="pointer-events-none absolute -translate-x-1/2 rounded-[3px] bg-[rgba(12,14,13,.72)] px-[3px] font-mono text-[9px] leading-[13px] text-chalk" style={{ left: pos(U(p.u), p.v).left, top: `calc(${pos(U(p.u), p.v).top} + 11px)` }}>
            {p.height!.toFixed(2)}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-[10px]">
        <OutcomeIcon kind={c.outcome.kind} />
        <div className="min-w-0 text-[15px] font-semibold [text-wrap:pretty]">{cornerOutcome(c.outcome.text, lang)}</div>
      </div>
    </article>
  );
}

type SummaryProps = { corners: Corner[]; cup: Lineups['cup']; players: LineupPlayer[]; range: string };

/** Corners per team so far (Analyst mode, on top of the Line-ups tab): sides, delivery zones, main target, goals. */
const ZONE: Record<Corner['zone'], Key> = { near: 'nearPost', far: 'farPost', spot: 'penaltySpot', short: 'short' };

export function CornerSummary({ corners, cup, players, range }: SummaryProps) {
  const teams = useTeams();
  const { t: tr } = useLang();
  const column = (team: TeamId) => {
    const own = corners.filter((c) => c.team === team);
    const left = own.filter((c) => c.side === 'left').length;
    const zones = (['near', 'far', 'spot', 'short'] as const).map((z) => ({ z, v: own.filter((c) => c.zone === z).length }));
    const zmax = Math.max(1, ...zones.map((z) => z.v));
    const aimed = own.filter((c) => c.zone !== 'short');
    const counts = new Map<string, number>();
    for (const c of aimed) if (c.firstTouch.team === team && c.firstTouch.id) counts.set(c.firstTouch.id, (counts.get(c.firstTouch.id) ?? 0) + 1);
    const [targetId, hits] = [...counts.entries()].sort((a, b) => b[1] - a[1])[0] ?? [null, 0];
    const target = players.find((p) => p.id === targetId);
    return { team, total: own.length, left, right: own.length - left, zones, zmax, aimed: aimed.length, target, hits,
      goals: own.filter((c) => c.outcome.kind === 'goal').length, cupGoals: cup?.cornerGoals[team] };
  };
  const cols = [column(teams.home.id), column(teams.away.id)];

  return (
    <section className="box-border flex w-full flex-col gap-4 rounded-lg border border-line bg-surface px-[18px] pb-[18px] pt-4" aria-label={tr('corners')}>
      <header className="flex items-center gap-3">
        <FlagBox />
        <div className="font-display text-card-type font-extrabold uppercase leading-none tracking-[.05em]">{tr('corners')}</div>
        <div className="ml-auto font-mono text-label uppercase tracking-[.08em] text-fg-3">{range} · {tr('eventData')}</div>
      </header>
      <div className="grid grid-cols-2 gap-5">
        {cols.map((t) => (
          <div key={t.team} className="flex min-w-0 flex-col gap-[14px]">
            <div className="flex items-center gap-2 font-mono text-[13px] text-fg-2">
              <span className="inline-block h-3 w-3 rounded-[3px]" style={{ background: teams.color(t.team) }} />
              {teams.short(t.team)}
            </div>
            <div className="flex items-end gap-[10px]">
              <div className="font-display text-[48px] font-extrabold leading-[.85]">{t.total}</div>
              <div className="flex min-w-0 flex-1 flex-col gap-[5px] pb-[2px]">
                <div className="flex justify-between gap-2 font-mono text-[12px] text-fg-2"><span>{tr('left')} {t.left}</span><span>{tr('right')} {t.right}</span></div>
                <div className="flex h-[6px] gap-[3px]">
                  {t.total === 0 && <div className="flex-1 rounded-full bg-surface-2" />}
                  {t.left > 0 && <div className="rounded-full" style={{ flex: t.left, background: teams.color(t.team) }} />}
                  {t.right > 0 && <div className="rounded-full opacity-[.45]" style={{ flex: t.right, background: teams.color(t.team) }} />}
                </div>
              </div>
            </div>
            <div className="flex flex-col gap-[6px]">
              <div className="font-mono text-label uppercase tracking-[.12em] text-fg-3">{tr('deliveryZone')}</div>
              {t.zones.map(({ z, v }) => (
                <div key={z} className="grid grid-cols-[minmax(0,112px)_minmax(0,1fr)_16px] items-center gap-2 text-[13px]">
                  <span className={`truncate ${v ? 'text-fg' : 'text-fg-3'}`}>{tr(ZONE[z])}</span>
                  <span className="h-2 overflow-hidden rounded-full bg-surface-2"><span className="block h-full rounded-full" style={{ width: `${(v / t.zmax) * 100}%`, background: teams.color(t.team) }} /></span>
                  <span className="text-right font-mono text-[12px]">{v}</span>
                </div>
              ))}
            </div>
            <div className="flex flex-col gap-[6px]">
              <div className="font-mono text-label uppercase tracking-[.12em] text-fg-3">{tr('mainTarget')}</div>
              {t.target ? (
                <div className="flex min-w-0 items-center gap-2">
                  <Chip p={t.target} size={24} />
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate text-[14px] font-semibold">{t.target.name}</span>
                    <span className="font-mono text-label text-fg-3">{tr('firstContacts', { h: t.hits, n: t.aimed })}</span>
                  </div>
                </div>
              ) : (
                <span className="text-[13px] text-fg-3">{t.total ? tr('noFirstContact') : tr('noCorners')}</span>
              )}
            </div>
            <div className="flex flex-col gap-[6px]">
              <div className="font-mono text-label uppercase tracking-[.12em] text-fg-3">{tr('goalsFromCorners')}</div>
              <div className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-line bg-line">
                <div className="flex flex-col bg-surface px-[10px] py-[6px]"><span className="font-display text-[24px] font-extrabold leading-none">{t.goals}</span><span className="font-mono text-label text-fg-3">{tr('thisMatch')}</span></div>
                <div className="flex flex-col bg-surface px-[10px] py-[6px]"><span className="font-display text-[24px] font-extrabold leading-none">{t.cupGoals ?? '–'}</span><span className="font-mono text-label text-fg-3">{tr('cupShort')}</span></div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
