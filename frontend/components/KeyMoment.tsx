import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { Insight, MatchEvent, MatchStats } from '@/lib/contracts';
import { useLang, type Key } from '@/lib/i18n';
import { InsightCard } from './InsightCard';
import { useTeams } from '@/lib/teams';
import { Crest, Stopwatch } from './icons';

type Props = {
  event: MatchEvent;
  insight?: Insight;
  stats: MatchStats;
  mode: 'casual' | 'analyst';
  /** true for the 480 ms in which the hero card moves to the feed */
  exiting: boolean;
};

const BAR_LABEL: Record<MatchEvent['kind'], Key> = { goal: 'barGoal', bigchance: 'barBigchance', yellow: 'barCard', red: 'barRed', sub: 'barSub' };

const HERO_GAP = 12;     // px between the detail pill and the hero card
const HERO_BOTTOM = 28;  // bottom-7
const touch = (a: DOMRect, b: DOMRect) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

/** The bar (GOAL / CARD / RED CARD) stays at the top; the status pills give way so they never cover it:
 *  'full' pills, then 'compact' pills (icon + 1×), and only if even that does not fit, the bar moves below them. */
type Fit = 'full' | 'compact' | 'below';

/** TV-director layer over the pitch while the backend has slowed to 1×. */
export function KeyMoment({ event, insight, stats, mode, exiting }: Props) {
  const teams = useTeams();
  const { t } = useLang();
  const team = event.team;
  const info = teams.info(team) ?? teams.home;
  const side = teams.side(team) ?? 'home';
  const [fit, setFit] = useState<Fit>('full');
  const pill = useRef<HTMLDivElement>(null);
  const replay = useRef<HTMLDivElement>(null);
  const bar = useRef<HTMLDivElement>(null);
  const top = useRef<HTMLDivElement>(null);        // the bar plus the detail pill under it
  const heroBox = useRef<HTMLDivElement>(null);
  // The hero card must stay below the bar and its detail pill: 0 full, 1 smaller text, 2 no evidence, 3 capped height.
  const [heroFit, setHeroFit] = useState<0 | 1 | 2 | 3>(0);

  // Start from the full pills for every new key moment and after every resize, then step down while they touch.
  useEffect(() => {
    setFit('full');
    setHeroFit(0);
    const reset = () => { setFit('full'); setHeroFit(0); };
    window.addEventListener('resize', reset);
    return () => window.removeEventListener('resize', reset);
  }, [event.id]);
  useLayoutEffect(() => {
    if (!pill.current || !replay.current || !bar.current || fit === 'below') return;
    const b = bar.current.getBoundingClientRect();
    if (touch(pill.current.getBoundingClientRect(), b) || touch(replay.current.getBoundingClientRect(), b)) {
      setFit(fit === 'full' ? 'compact' : 'below');
    }
  });
  // The hero grows while its text streams in: measure after every render, only ever step down per key moment.
  useLayoutEffect(() => {
    if (!top.current || !heroBox.current || heroFit === 3) return;
    if (heroBox.current.getBoundingClientRect().top < top.current.getBoundingClientRect().bottom + HERO_GAP) {
      setHeroFit((heroFit + 1) as 1 | 2 | 3);
    }
  });
  const heroMaxHeight = (): string | undefined => {
    if (heroFit < 3 || !top.current || !heroBox.current?.parentElement) return undefined;
    const box = heroBox.current.parentElement.getBoundingClientRect();
    const room = box.bottom - HERO_BOTTOM - (top.current.getBoundingClientRect().bottom + HERO_GAP);
    return `${Math.max(120, room)}px`;
  };
  const compact = fit !== 'full';
  return (
    <>
      <div className={`pointer-events-none absolute inset-0 bg-black/[.24] transition-opacity duration-[480ms] ${exiting ? 'opacity-0' : 'itg-fade'}`} />

      {/* The status pills, at the top corners. They give way to the bar (see Fit). */}
      <div className="pointer-events-none absolute inset-x-7 top-7 flex items-start justify-between gap-3">
        <div
          ref={pill}
          title={t('keyMoment')}
          aria-label={t('keyMoment')}
          className={`flex items-center gap-2 whitespace-nowrap rounded-full bg-chalk py-2 pl-[10px] pr-[14px] text-[15px] font-semibold text-ink transition-opacity duration-[480ms] ${exiting ? 'opacity-0' : 'itg-in'}`}
        >
          <Stopwatch size={18} />
          {compact ? '1×' : t('keyMoment')}
        </div>
        <div
          ref={replay}
          title={t('replayTag')}
          aria-label={t('replayTag')}
          className={`flex items-center gap-2 rounded-full bg-[rgba(12,14,13,.88)] px-[14px] py-2 font-mono text-[13px] tracking-[.12em] text-chalk transition-opacity duration-[480ms] ${exiting ? 'opacity-0' : 'itg-in'}`}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M11 19 2 12l9-7v14ZM22 19l-9-7 9-7v14Z" /></svg>
          {!compact && t('replayTag').toUpperCase()}
        </div>
      </div>

      <div className={`absolute left-1/2 ${fit === 'below' ? 'top-[76px]' : 'top-7'} flex -translate-x-1/2 flex-col items-center gap-[10px] transition-opacity duration-[480ms] ${exiting ? 'opacity-0' : 'itg-in'}`} ref={top}>
        <div ref={bar} className="flex h-16 overflow-hidden rounded-md shadow-[0_12px_32px_rgba(0,0,0,.45)]">
          <div className="flex items-center whitespace-nowrap bg-chalk px-6 font-display text-tv-bar font-extrabold tracking-[.08em] text-ink">{t(BAR_LABEL[event.kind]).toUpperCase()}</div>
          <div
            className="flex items-center gap-3 whitespace-nowrap pl-[18px] pr-6 font-display text-[38px] font-extrabold tracking-[.02em]"
            style={{ background: info.color, color: info.fg }}
          >
            <Crest team={info} side={side} small />
            {teams.label(team)} {stats.score[0]}-{stats.score[1]}
          </div>
          <div className="flex items-center whitespace-nowrap bg-ink px-[22px] font-display text-[38px] font-extrabold text-chalk">{event.minute}&apos;</div>
        </div>
        {event.detail && (
          <div className="rounded-full bg-[rgba(12,14,13,.88)] px-[14px] py-[6px] text-[15px] text-chalk">{event.detail}</div>
        )}
      </div>


      {insight && (
        <div
          ref={heroBox}
          className={`absolute bottom-7 left-7 w-[min(700px,calc(100%-56px))] origin-top-right ${heroFit === 3 ? 'overflow-hidden rounded-lg' : ''} transition-[transform,opacity] duration-[480ms] ease-out ${exiting ? 'translate-x-[45%] -translate-y-[85%] scale-[.6] opacity-0' : 'itg-in'}`}
          style={{ maxHeight: heroMaxHeight() }}
        >
          <InsightCard insight={insight} size="hero" mode={mode} dense={Math.min(heroFit, 2) as 0 | 1 | 2} />
        </div>
      )}
    </>
  );
}
