'use client';

import { useLang } from '@/lib/i18n';
import { playerFocus, type Lineups } from '@/lib/lineups';
import { usePreferences } from '@/lib/preferences';
import { useTeams } from '@/lib/teams';
import { ArrowDown, ArrowUp, CardIcon, Chip } from './Lineups';

function Num({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-[2px] bg-surface px-3 py-[8px]">
      <div className="font-display text-[22px] font-extrabold leading-none">{v}</div>
      <div className="truncate font-mono text-label uppercase tracking-[.04em] text-fg-3">{k}</div>
    </div>
  );
}

/** The followed player at the top of the right column: one row (collapsed) or with four live numbers.
 *  Four states from the line-up data: on the pitch, subbed off, sent off, on the bench. */
export function PlayerStrip({ data, t, onOpen }: { data: Lineups; t: number; onOpen: (id: string) => void }) {
  const teams = useTeams();
  const { t: tr, role } = useLang();
  const { prefs, set, follow } = usePreferences();
  const f = prefs.playerId ? playerFocus(data, prefs.playerId, t) : null;
  if (!f) return null;
  const { player: p, status, stats } = f;
  const collapsed = prefs.stripCollapsed;
  const km = stats ? stats.km.toFixed(1) : '–';
  const summary = stats ? `${stats.touches} ${tr('touches').toLowerCase()} · ${km} km` : '';

  return (
    <section className="itg-fade box-border flex w-full flex-col gap-3 rounded-lg border border-line bg-surface px-4 py-2" aria-label={tr('followPlayer')}>
      <div className="flex min-h-11 items-center gap-3">
        <span className={`itg-player-ring flex-none rounded-full ${status === 'bench' ? 'border-2 border-dashed border-fg-3 opacity-60' : ''}`}
          style={{ opacity: status === 'off' ? 0.55 : undefined }}>
          <Chip p={p} size={32} />
        </span>
        <button type="button" onClick={() => onOpen(p.id)} className="flex min-h-11 min-w-0 flex-1 flex-col justify-center bg-transparent p-0 text-left">
          <span className="truncate text-[16px] font-semibold text-fg underline-offset-2 hover:underline">{p.name}</span>
          <span className="truncate font-mono text-label text-fg-2">
            {status === 'on' && summary}
            {status === 'off' && <span className="inline-flex items-center gap-1"><ArrowDown />{tr('subbedOff', { m: p.off!.minute })}</span>}
            {status === 'red' && <span className="inline-flex items-center gap-1"><CardIcon red w={8} h={11} />{tr('sentOff', { m: p.off!.minute })}</span>}
            {status === 'bench' && tr('onTheBench')}
          </span>
        </button>
        <button
          type="button"
          onClick={() => set({ stripCollapsed: !collapsed })}
          aria-expanded={!collapsed}
          aria-label={collapsed ? tr('showMore') : tr('showLess')}
          className="flex h-11 w-11 flex-none items-center justify-center rounded-full bg-transparent text-fg-2 hover:text-fg"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ transform: collapsed ? 'none' : 'rotate(180deg)' }} aria-hidden><path d="m6 9 6 6 6-6" /></svg>
        </button>
      </div>

      {!collapsed && (
        <div className="flex flex-col gap-3 pb-2">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-label uppercase tracking-[.08em] text-fg-2">
            <span>{p.role}</span><span>·</span>
            <span className="inline-flex items-center gap-1"><span className="inline-block h-[10px] w-[10px] rounded-[3px]" style={{ background: teams.color(p.team) }} />{teams.short(p.team)}</span>
            <span>·</span>
            {status === 'on' && <span className="inline-flex items-center gap-1 normal-case tracking-normal"><span className="h-2 w-2 rounded-full bg-corrected" />{tr('stripOnPitch')}</span>}
            {status !== 'on' && <span className="normal-case tracking-normal">{role(p.roleName)}</span>}
          </div>
          {status === 'bench' ? (
            <div className="text-[14px] text-fg-2">{tr('stripBench')}</div>
          ) : (
            <div className="grid grid-cols-4 gap-px overflow-hidden rounded-md border border-line bg-line">
              <Num k={tr('tileTouches')} v={stats ? String(stats.touches) : '–'} />
              <Num k={tr('passes')} v={stats ? `${stats.passes}/${stats.attempts}` : '–'} />
              <Num k={tr('sprints')} v={stats ? String(stats.sprints) : '–'} />
              <Num k={tr('km')} v={km} />
            </div>
          )}
          {status === 'red' && f.formationAfter && (
            <div className="font-mono text-label uppercase tracking-[.08em] text-fg-2">{teams.short(p.team)} · {tr('nowPlaying', { f: f.formationAfter })}</div>
          )}
        </div>
      )}

      {status === 'off' && f.replacedBy && (
        <div className="flex flex-wrap items-center gap-x-2 border-t border-line pb-1 pt-1 text-[14px] text-fg-2">
          <ArrowUp />
          <span>{tr('cameOn', { name: f.replacedBy.name })}</span>
          <span>·</span>
          <button type="button" onClick={() => follow(f.replacedBy!.id)} className="h-11 bg-transparent px-1 font-semibold text-fg hover:underline">
            ☆ {tr('followName', { name: f.replacedBy.name.split('. ').pop()! })}
          </button>
        </div>
      )}
    </section>
  );
}
