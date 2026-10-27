'use client';

import { useEffect, useRef, useState } from 'react';
import type { TeamId } from '@/lib/contracts';
import { LANGS, useLang } from '@/lib/i18n';
import type { LineupPlayer } from '@/lib/lineups';
import { usePreferences } from '@/lib/preferences';
import { useTeams } from '@/lib/teams';
import { Chip } from './Lineups';
import { Segmented } from './Segmented';

function PersonIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" aria-hidden>
      <circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" />
    </svg>
  );
}

/** A team colour block; in the day theme with a 1 px edge in the team's text colour. */
export function Swatch({ team, size = 10 }: { team: TeamId; size?: number }) {
  const teams = useTeams();
  return (
    <span
      className="itg-swatch inline-block flex-none rounded-[3px]"
      style={{ width: size, height: size, background: teams.color(team), ['--itg-swatch-text' as string]: teams.text(team) }}
      aria-hidden
    />
  );
}

const SectionTitle = ({ children }: { children: string }) => (
  <div className="font-mono text-label uppercase tracking-[.12em] text-fg-3">{children}</div>
);

/** "Your view": club, player, Casual/Analyst and language, next to the language picker. Saved on this device. */
export function ProfileMenu({ players }: { players: LineupPlayer[] }) {
  const teams = useTeams();
  const { t, lang, setLang, role } = useLang();
  const { prefs, set, reset, follow } = usePreferences();
  const [open, setOpen] = useState(false);
  const [picking, setPicking] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !box.current?.contains(e.target as Node)) { setOpen(false); setPicking(false); }
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', close); };
  }, [open]);

  const club = prefs.club;
  const player = players.find((p) => p.id === prefs.playerId);
  const teamOrder = [teams.home.id, teams.away.id];

  return (
    <div ref={box} className="relative flex-none">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={t('profile')}
        title={t('yourView')}
        className="relative -m-[2px] flex h-11 w-11 items-center justify-center rounded-full bg-transparent p-0 text-fg-2 hover:text-fg"
      >
        <span className="flex h-10 w-10 items-center justify-center rounded-full border border-line"><PersonIcon /></span>
        {club !== 'neutral' && (
          <span className="absolute bottom-[3px] right-[3px] h-[10px] w-[10px] rounded-full" style={{ background: teams.color(club), boxShadow: '0 0 0 2px var(--itg-bg)' }} aria-hidden />
        )}
        {player && (
          <span className="absolute right-[3px] top-[3px] h-[10px] w-[10px] rounded-full bg-accent" style={{ boxShadow: '0 0 0 2px var(--itg-bg)' }} aria-hidden />
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label={t('yourView')}
          className="itg-in absolute left-0 top-12 z-50 flex w-[380px] flex-col gap-4 rounded-lg border border-line-strong bg-surface p-4 shadow-[0_12px_32px_rgba(0,0,0,.35)]"
        >
          <div className="flex items-baseline justify-between gap-3">
            <div className="font-display text-[22px] font-extrabold uppercase leading-none tracking-[.05em]">{t('yourView')}</div>
            <div className="font-mono text-label text-fg-3">{t('savedOnDevice')}</div>
          </div>

          {!picking && (
            <>
              <div className="flex flex-col gap-2">
                <SectionTitle>{t('club')}</SectionTitle>
                <Segmented
                  label={t('club')}
                  value={club}
                  onChange={(v) => set({ club: v })}
                  options={[
                    ...teamOrder.map((id) => ({ value: id, label: <><Swatch team={id} />{teams.short(id)}</>, aria: teams.info(id)?.name })),
                    { value: 'neutral', label: t('neutral') },
                  ]}
                />
              </div>

              <div className="flex flex-col gap-2">
                <SectionTitle>{t('player')}</SectionTitle>
                <div className="flex min-h-11 items-center gap-3">
                  {player ? (
                    <>
                      <span className="itg-player-ring flex-none rounded-full"><Chip p={player} size={30} /></span>
                      <span className="flex min-w-0 flex-1 flex-col">
                        <span className="truncate text-[15px] font-semibold">{player.name}</span>
                        <span className="truncate font-mono text-label uppercase tracking-[.08em] text-fg-3">{role(player.roleName)} · {teams.short(player.team)}</span>
                      </span>
                    </>
                  ) : (
                    <span className="flex-1 text-[14px] text-fg-3">{t('noPlayer')}</span>
                  )}
                  <button type="button" onClick={() => setPicking(true)} className="h-11 flex-none whitespace-nowrap rounded-full border border-line px-3 text-[14px] font-semibold text-fg hover:bg-surface-2">
                    {t('change')}
                  </button>
                  {player && (
                    <button type="button" onClick={() => follow(null)} className="h-11 flex-none whitespace-nowrap rounded-full px-2 text-[14px] font-semibold text-fg-2 hover:text-fg">
                      {t('stopFollowing')}
                    </button>
                  )}
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <SectionTitle>{t('viewLabel')}</SectionTitle>
                <Segmented label={t('explanationStyle')} value={prefs.mode} onChange={(v) => set({ mode: v })}
                  options={[{ value: 'casual', label: t('casual') }, { value: 'analyst', label: t('analyst') }]} />
              </div>

              <div className="flex flex-col gap-2">
                <SectionTitle>{t('language')}</SectionTitle>
                <Segmented label={t('language')} value={lang} onChange={setLang} size="sm"
                  options={LANGS.map((l) => ({ value: l.code, label: l.code.toUpperCase(), aria: l.name }))} />
              </div>

              <div className="flex justify-end border-t border-line pt-3">
                <button type="button" onClick={() => reset()} className="h-11 whitespace-nowrap rounded-full px-3 text-[14px] font-semibold text-fg-2 hover:text-fg">
                  {t('resetNeutral')}
                </button>
              </div>
            </>
          )}

          {picking && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between gap-3">
                <SectionTitle>{t('choosePlayer')}</SectionTitle>
                <button type="button" onClick={() => setPicking(false)} className="h-11 rounded-full px-3 text-[14px] font-semibold text-fg-2 hover:text-fg">{t('back')}</button>
              </div>
              <div className="flex max-h-[360px] flex-col overflow-y-auto overflow-x-hidden">
                {teamOrder.map((team) => (
                  <div key={team} className="flex flex-col">
                    <div className="flex items-center gap-2 pb-1 pt-2 font-mono text-label uppercase tracking-[.12em] text-fg-3"><Swatch team={team} />{teams.label(team)}</div>
                    {players.filter((p) => p.team === team).sort((a, b) => Number(b.starter) - Number(a.starter) || a.n - b.n).map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => { follow(p.id); setPicking(false); }}
                        aria-pressed={prefs.playerId === p.id}
                        className={`grid h-11 w-full grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-3 rounded-sm border-b border-line px-2 text-left hover:bg-surface-2 ${prefs.playerId === p.id ? 'bg-surface-2' : 'bg-transparent'}`}
                      >
                        <Chip p={p} size={26} />
                        <span className="truncate text-[15px] font-semibold">{p.name}</span>
                        <span className="font-mono text-[12px] text-fg-3">{p.role}</span>
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
