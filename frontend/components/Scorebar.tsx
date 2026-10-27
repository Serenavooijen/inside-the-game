'use client';

import type { MatchEvent, MatchStats, Mode } from '@/lib/contracts';
import { useLang } from '@/lib/i18n';
import { usePreferences } from '@/lib/preferences';
import { useTeams } from '@/lib/teams';
import { AwayCrest, HomeCrest, Logo, SmallBall, SubIcon } from './icons';
import { LanguagePicker } from './Language';
import { ProfileMenu } from './ProfileMenu';
import type { LineupPlayer } from '@/lib/lineups';
import { ThemeToggle } from './ThemeToggle';

type Props = {
  stats: MatchStats;
  clock: string;
  period: string;
  mode: Mode;
  /** Most recent first is not required; the bar shows the last four */
  events: MatchEvent[];
  /** the squads, for "Your view" (favourite club and player); without them there is no profile button */
  players?: LineupPlayer[];
};

export function Scorebar({ stats, clock, period, mode, events, players }: Props) {
  const teams = useTeams();
  const { t } = useLang();
  const { isMyClub } = usePreferences();
  // "★ YOUR CLUB" under your club's bar: team colour with the team's own foreground for contrast
  const clubTab = (id: string, fg: string) => isMyClub(id) && (
    <span className="pointer-events-none absolute left-1/2 top-[calc(100%-4px)] z-[1] flex h-[18px] -translate-x-1/2 items-center whitespace-nowrap rounded-b-sm px-2 font-mono text-[11px] font-medium uppercase leading-none tracking-[.08em]"
      style={{ background: teams.color(id), color: fg }}>
      ★ {t('yourClub')}
    </span>
  );
  const recent = events.filter((e) => e.kind !== 'bigchance').slice(-4);
  const [possH, possA] = stats.possession;
  const [xgH, xgA] = stats.xg;
  return (
    <header className={`grid h-[104px] flex-none items-center gap-8 border-b border-line bg-bg px-10 ${players ? 'grid-cols-[auto_auto_auto] justify-between min-[1600px]:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]' : 'grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]'}`}>
      <div className="flex min-w-0 items-center gap-3">
        <a href="/" className="flex flex-none items-center gap-[10px] whitespace-nowrap" aria-label="Inside the Game, back to the match list">
          <Logo />
          <span className="font-display text-[28px] font-extrabold uppercase leading-none tracking-[.04em] max-[1439px]:hidden">Inside the Game</span>
        </a>
        {mode === 'live' ? (
          <div className="flex flex-none items-center gap-2 whitespace-nowrap rounded-full bg-surface-2 px-3 py-[6px] text-[14px] font-semibold">
            <span className="itg-live inline-block h-[9px] w-[9px] rounded-full bg-corrected" />
            {t('live')}
          </div>
        ) : (
          <div className="flex flex-none items-center gap-[10px] whitespace-nowrap rounded-full border border-line-strong py-[6px] pl-[10px] pr-[14px] text-[14px] font-semibold">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
              <path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" />
            </svg>
            {t('replay')}
            <span className="font-mono text-[12px] font-medium text-fg-3">{t('noLiveAi')}</span>
          </div>
        )}
        <div className="flex flex-none items-center gap-2">
          <ThemeToggle />
          <LanguagePicker />
          {players && <ProfileMenu players={players} />}
        </div>
      </div>

      <div className={`flex flex-col items-center ${isMyClub(teams.home.id) || isMyClub(teams.away.id) ? 'gap-[16px]' : 'gap-[6px]'}`}>
        <div className="flex h-[60px] flex-none items-stretch whitespace-nowrap rounded-md bg-surface-2 shadow-[0_4px_12px_rgba(0,0,0,.25)]">
          <div className="relative flex items-center gap-3 rounded-l-md border-b-[5px] border-home pl-[14px] pr-[18px]">
            {clubTab(teams.home.id, teams.home.fg)}
            <HomeCrest color={teams.home.color} fg={teams.home.fg} />
            <span className="font-display text-[32px] font-extrabold tracking-[.04em]">{teams.home.short}</span>
          </div>
          <div
            className="flex items-center gap-[14px] bg-fg px-[22px] font-display text-score font-extrabold leading-none text-bg"
            aria-label={`Score ${stats.score[0]} – ${stats.score[1]}`}
          >
            <span>{stats.score[0]}</span>
            <span className="text-[28px] opacity-50">–</span>
            <span>{stats.score[1]}</span>
          </div>
          <div className="relative flex items-center gap-3 border-b-[5px] border-away pl-[18px] pr-[14px]">
            {clubTab(teams.away.id, teams.away.fg)}
            <span className="font-display text-[32px] font-extrabold tracking-[.04em]">{teams.away.short}</span>
            <AwayCrest color={teams.away.color} fg={teams.away.fg} />
          </div>
          <div className="flex min-w-[96px] flex-col items-center justify-center rounded-r-md border-l border-line px-[18px]">
            <span className="font-mono text-[24px] font-medium leading-none">{clock}</span>
            <span className="mt-1 font-mono text-[11px] tracking-[.12em] text-fg-3">{period}</span>
          </div>
        </div>
        <div className={`flex h-[18px] items-center gap-[18px] text-[13px] text-fg-2 ${players ? 'w-0 min-w-full justify-center whitespace-nowrap' : ''}`}>
          {recent.map((e) => (
            <div key={e.id} className="flex items-center gap-[6px]">
              {e.kind === 'goal' && <SmallBall />}
              {e.kind === 'yellow' && <span className="inline-block h-[11px] w-2 rounded-[2px] bg-card-yellow" />}
              {e.kind === 'red' && <span className="inline-block h-[11px] w-2 rounded-[2px] bg-card-red" />}
              {e.kind === 'sub' && <SubIcon />}
              <span className="inline-block h-[6px] w-[6px] rounded-[2px]" style={{ background: teams.color(e.team) }} />
              <span>{e.text}</span>
            </div>
          ))}
        </div>
      </div>

      <div className={`flex items-center justify-end ${players ? 'gap-6 min-[1600px]:gap-10' : 'gap-10'}`}>
        <div className="flex w-[200px] flex-col gap-[6px]">
          <div className="flex items-baseline justify-between">
            <span className="font-display text-[26px] font-bold leading-none">{possH}%</span>
            <span className="font-mono text-label uppercase tracking-[.12em] text-fg-3">{t('possession')}</span>
            <span className="font-display text-[26px] font-bold leading-none">{possA}%</span>
          </div>
          <div className="flex h-[6px] gap-[3px]">
            <div className="rounded-full bg-home" style={{ flex: possH }} />
            <div className="rounded-full bg-away" style={{ flex: possA }} />
          </div>
        </div>
        <div className="flex flex-col items-center gap-[6px]">
          <div className="flex items-baseline gap-[14px] font-display text-[26px] font-bold leading-none">
            <span>{xgH.toFixed(2)}</span>
            <span className="font-mono text-label font-medium tracking-[.12em] text-fg-3">XG</span>
            <span>{xgA.toFixed(2)}</span>
          </div>
          <div className="flex h-[6px] w-[120px] gap-[3px]">
            <div className="rounded-full bg-home" style={{ flex: Math.max(xgH, 0.01) }} />
            <div className="rounded-full bg-away" style={{ flex: Math.max(xgA, 0.01) }} />
          </div>
        </div>
      </div>
    </header>
  );
}
