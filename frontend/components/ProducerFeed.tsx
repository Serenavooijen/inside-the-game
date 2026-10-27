'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { Insight, ScoutingReport } from '@/lib/contracts';
import type { Corner } from '@/lib/lineups';
import { feedItems, insightTeam, type FeedFilter, type FocusPlayer } from '@/lib/feed';
import { usePreferences } from '@/lib/preferences';
import { Segmented } from './Segmented';
import { useLang } from '@/lib/i18n';
import { useTeams } from '@/lib/teams';
import { CornerCard } from './Corners';
import { InsightCard } from './InsightCard';
import { SubstitutionCard } from './SubstitutionCard';
import { ScoutingReportPanel, TacticsCard } from './TacticsCard';

type Props = {
  insights: Insight[];
  mode: 'casual' | 'analyst';
  onMode: (m: 'casual' | 'analyst') => void;
  /** id of the card that just arrived from the hero (animates in) */
  arrivingId?: string | null;
  /** "<insight id>:<nonce>" scrolls that card into view (e.g. from the fact-check pill) */
  focusId?: string | null;
  /** The Scout's report on the cup match (backend with TACTICS_ENABLED=1) */
  scouting?: ScoutingReport;
  /** the checked translations of the scouting card in the feed: the same observations as the report */
  scoutingTranslations?: Insight['translations'];
  tab: FeedTab;
  onTab: (tab: FeedTab) => void;
  /** Corners so far (made by code from the event data); they sit in the feed in both modes */
  corners?: Corner[];
  /** Content of the Line-ups tab; without it the tab is not shown */
  lineups?: ReactNode;
  /** Player analysis: fills the column, without the title and the tabs */
  player?: ReactNode;
  /** the followed player, for the filter "My player" */
  focusPlayer?: FocusPlayer | null;
  /** the followed player's strip, at the top of the column */
  strip?: ReactNode;
};

export type FeedTab = 'feed' | 'scouting' | 'lineups';

/** Smart lane: newest first, newest card open. Tactics cards only in Analyst mode. */
export function ProducerFeed({ insights, mode, onMode, arrivingId, focusId, scouting, scoutingTranslations, tab, onTab, corners = [], lineups, player, focusPlayer = null, strip }: Props) {
  const teams = useTeams();
  const { t } = useLang();
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const refs = useRef<Record<string, HTMLDivElement | null>>({});
  const { prefs, emphasis, myClubColor } = usePreferences();
  // My club / My player: only the options that fit your choice; without a choice there is no filter row
  const [filter, setFilter] = useState<FeedFilter>('all');
  const filters: FeedFilter[] = ['all', ...(prefs.club !== 'neutral' ? ['club' as const] : []), ...(focusPlayer ? ['player' as const] : [])];
  const active: FeedFilter = filters.includes(filter) ? filter : 'all';
  const sel = (f: FeedFilter) => ({ filter: f, club: prefs.club, player: focusPlayer });
  const list = feedItems(insights, corners, mode, sel(active));
  const newest = list.flatMap((x) => (x.kind === 'insight' ? [x.insight.id] : []))[0];

  useEffect(() => {
    if (!focusId) return;
    const id = focusId.split(':')[0];
    onTab('feed');
    setOpen((o) => ({ ...o, [id]: true }));
    refs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusId]);

  const seg = (m: 'casual' | 'analyst', label: string) => (
    <button
      type="button"
      onClick={() => onMode(m)}
      aria-pressed={mode === m}
      className={`h-[34px] whitespace-nowrap rounded-sm px-3 text-[14px] font-semibold ${mode === m ? 'bg-fg text-bg' : 'bg-transparent text-fg-2 hover:text-fg'}`}
    >
      {label}
    </button>
  );

  const shown: FeedTab = tab === 'scouting' && !scouting ? 'feed' : tab === 'lineups' && !lineups ? 'feed' : tab;
  const tabs = ([['feed', t('tabFeed')], ['scouting', t('tabScouting')], ['lineups', t('tabLineups')]] as const)
    .filter(([k]) => k === 'feed' || (k === 'scouting' ? !!scouting : !!lineups));
  const title = shown === 'scouting' ? [t('scouting'), t('cupBeforeKickoff')]
    : shown === 'lineups' ? [t('lineups'), `${teams.label(teams.home.id)} ${t('vs')} ${teams.label(teams.away.id)}`]
      : [t('producerFeed'), t('newestFirst')];

  return (
    <section className="flex min-w-[400px] flex-1 basis-0 flex-col gap-4" aria-label="Producer feed">
      {/* Never cut or break the titles: when the column is narrow the mode switch moves to its own line. */}
      {!player && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-col gap-[2px]">
            <h2 className="whitespace-nowrap font-display text-[28px] font-extrabold uppercase leading-none tracking-[.04em]">{title[0]}</h2>
            <div className="whitespace-nowrap font-mono text-label uppercase tracking-[.12em] text-fg-3">{title[1]}</div>
          </div>
          <div className="flex flex-none gap-[2px] rounded-md bg-surface-2 p-[3px]" role="group" aria-label={t('explanationStyle')}>
            {seg('casual', t('casual'))}
            {seg('analyst', t('analyst'))}
          </div>
        </div>
      )}
      {!player && tabs.length > 1 && (
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Feed, scouting report or line-ups">
          {tabs.map(([k, label]) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={shown === k}
              onClick={() => onTab(k)}
              className={`h-[34px] whitespace-nowrap rounded-full border px-[14px] text-[14px] font-semibold ${shown === k ? 'border-fg text-fg' : 'border-line text-fg-2 hover:text-fg'}`}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      {!player && strip}
      {!player && shown === 'feed' && filters.length > 1 && (
        <Segmented
          label={t('feedFilter')}
          value={active}
          onChange={setFilter}
          size="sm"
          options={filters.map((f) => ({
            value: f,
            label: <>{f === 'club' ? `★ ${t('filterClub')}` : f === 'player' ? `◎ ${t('filterPlayer')}` : t('filterAll')}
              <span className="opacity-60">{feedItems(insights, corners, mode, sel(f)).length}</span></>,
          }))}
        />
      )}
      <div className="relative min-h-0 flex-1 overflow-hidden">
        <div className="flex h-full flex-col gap-3 overflow-y-auto overflow-x-hidden pb-16 [scrollbar-width:none]">
          {player}
          {!player && shown === 'scouting' && scouting && <ScoutingReportPanel report={scouting} translations={scoutingTranslations} />}
          {!player && shown === 'lineups' && lineups}
          {!player && shown === 'feed' && list.length === 0 && (
            <div className="rounded-lg border border-dashed border-line px-[22px] py-5 text-[15px] text-fg-3">
              {t('emptyFeed')}
            </div>
          )}
          {!player && shown === 'feed' && list.map((x) => {
            // your club: a left edge in the team colour; the opponent: quieter, never hidden
            const emph = (team?: string) => {
              const e = emphasis(team);
              return e === 'mine' ? 'itg-emph-mine' : e === 'opponent' ? 'itg-emph-opponent' : '';
            };
            const emphStyle = { ['--itg-emph' as string]: myClubColor() } as React.CSSProperties;
            if (x.kind === 'corner') return <div key={x.corner.id} className={`itg-in ${emph(x.corner.team)}`} style={emphStyle}><CornerCard corner={x.corner} /></div>;
            const i = x.insight;
            const isOpen = open[i.id] ?? i.id === newest;
            const toggle = () => setOpen((o) => ({ ...o, [i.id]: !isOpen }));
            return (
              <div key={i.id} ref={(el) => { refs.current[i.id] = el; }} style={emphStyle}
                className={[i.id === arrivingId ? 'itg-arrive' : i.type === 'tactics' || i.type === 'substitution' ? 'itg-in' : '', emph(insightTeam(i))].join(' ').trim() || undefined}>
                {i.type === 'tactics'
                  ? <TacticsCard insight={i} expanded={isOpen} onToggle={toggle} />
                  : i.type === 'substitution'
                    ? <SubstitutionCard insight={i} expanded={isOpen} onToggle={toggle} />
                    : <InsightCard insight={i} mode={mode} expanded={isOpen} onToggle={toggle} />}
              </div>
            );
          })}
        </div>
        <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-14 bg-gradient-to-b from-transparent to-bg" />
      </div>
    </section>
  );
}
