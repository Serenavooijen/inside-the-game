import type { Insight, MatchEvent, MatchStats } from '@/lib/contracts';
import { InsightCard } from './InsightCard';
import { Crest, Stopwatch } from './icons';

type Props = {
  event: MatchEvent;
  insight?: Insight;
  stats: MatchStats;
  mode: 'casual' | 'analyst';
  /** true for the 480 ms in which the hero card moves to the feed */
  exiting: boolean;
};

const NAME = { kba: 'Kingsbridge', ngr: 'Northgate' } as const;
const BAR_LABEL: Record<MatchEvent['kind'], string> = { goal: 'GOAL', bigchance: 'BIG CHANCE', yellow: 'CARD', red: 'RED CARD', sub: 'SUB' };

/** TV-director layer over the pitch while the backend has slowed to 1×. */
export function KeyMoment({ event, insight, stats, mode, exiting }: Props) {
  const team = event.team;
  return (
    <>
      <div className={`pointer-events-none absolute inset-0 bg-black/[.24] transition-opacity duration-[480ms] ${exiting ? 'opacity-0' : 'itg-fade'}`} />

      <div className={`absolute left-1/2 top-7 flex -translate-x-1/2 flex-col items-center gap-[10px] transition-opacity duration-[480ms] ${exiting ? 'opacity-0' : 'itg-in'}`}>
        <div className="flex h-16 overflow-hidden rounded-md shadow-[0_12px_32px_rgba(0,0,0,.45)]">
          <div className="flex items-center whitespace-nowrap bg-chalk px-6 font-display text-tv-bar font-extrabold tracking-[.08em] text-ink">{BAR_LABEL[event.kind]}</div>
          <div
            className="flex items-center gap-3 whitespace-nowrap pl-[18px] pr-6 font-display text-[38px] font-extrabold tracking-[.02em]"
            style={{ background: team === 'kba' ? '#2F6BFF' : '#FFB400', color: team === 'kba' ? '#FFFFFF' : '#121212' }}
          >
            <Crest team={team} small />
            {NAME[team]} {stats.score[0]}-{stats.score[1]}
          </div>
          <div className="flex items-center whitespace-nowrap bg-ink px-[22px] font-display text-[38px] font-extrabold text-chalk">{event.minute}&apos;</div>
        </div>
        {event.detail && (
          <div className="rounded-full bg-[rgba(12,14,13,.88)] px-[14px] py-[6px] text-[15px] text-chalk">{event.detail}</div>
        )}
      </div>

      <div className={`absolute left-7 top-7 flex items-center gap-2 rounded-full bg-chalk py-2 pl-[10px] pr-[14px] text-[15px] font-semibold text-ink transition-opacity duration-[480ms] ${exiting ? 'opacity-0' : 'itg-in'}`}>
        <Stopwatch size={18} />
        Key moment · slowed to 1×
      </div>
      <div className={`absolute right-7 top-7 flex items-center gap-2 rounded-full bg-[rgba(12,14,13,.88)] px-[14px] py-2 font-mono text-[13px] tracking-[.12em] text-chalk transition-opacity duration-[480ms] ${exiting ? 'opacity-0' : 'itg-in'}`}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M11 19 2 12l9-7v14ZM22 19l-9-7 9-7v14Z" /></svg>
        REPLAY
      </div>

      {insight && (
        <div
          className={`absolute bottom-7 left-7 w-[min(700px,calc(100%-56px))] origin-top-right transition-[transform,opacity] duration-[480ms] ease-out ${exiting ? 'translate-x-[45%] -translate-y-[85%] scale-[.6] opacity-0' : 'itg-in'}`}
        >
          <InsightCard insight={insight} size="hero" mode={mode} />
        </div>
      )}
    </>
  );
}
