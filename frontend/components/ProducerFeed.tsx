'use client';

import { useEffect, useRef, useState } from 'react';
import type { Insight, ScoutingReport } from '@/lib/contracts';
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
};

/** Smart lane: newest first, newest card open. Tactics cards only in Analyst mode. */
export function ProducerFeed({ insights, mode, onMode, arrivingId, focusId, scouting }: Props) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [showReport, setShowReport] = useState(false);
  const refs = useRef<Record<string, HTMLDivElement | null>>({});
  const list = [...insights]
    .filter((i) => mode === 'analyst' || i.type !== 'tactics')
    .sort((a, b) => b.t - a.t)
    .slice(0, 14);
  const newest = list[0]?.id;

  useEffect(() => {
    if (!focusId) return;
    const id = focusId.split(':')[0];
    setShowReport(false);
    setOpen((o) => ({ ...o, [id]: true }));
    refs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
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

  const reportOpen = showReport && !!scouting;

  return (
    <section className="flex min-w-[400px] flex-1 basis-0 flex-col gap-4" aria-label="Producer feed">
      {/* Never cut or break the titles: when the column is narrow the mode switch moves to its own line. */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-[2px]">
          <h2 className="whitespace-nowrap font-display text-[28px] font-extrabold uppercase leading-none tracking-[.04em]">{reportOpen ? 'Scouting' : 'Producer feed'}</h2>
          <div className="whitespace-nowrap font-mono text-label tracking-[.12em] text-fg-3">{reportOpen ? 'THE CUP MATCH, BEFORE KICK-OFF' : 'NEWEST FIRST'}</div>
        </div>
        <div className="flex flex-none gap-[2px] rounded-md bg-surface-2 p-[3px]" role="group" aria-label="Explanation style">
          {seg('casual', 'Casual fan')}
          {seg('analyst', 'Analyst')}
        </div>
      </div>
      {scouting && (
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Feed or scouting report">
          {([[false, 'Feed'], [true, 'Scouting report (cup)']] as const).map(([report, label]) => (
            <button
              key={label}
              type="button"
              role="tab"
              aria-selected={showReport === report}
              onClick={() => setShowReport(report)}
              className={`whitespace-nowrap rounded-full border px-3 py-[5px] text-[14px] font-medium ${showReport === report ? 'border-fg text-fg' : 'border-line text-fg-2 hover:text-fg'}`}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      <div className="relative min-h-0 flex-1 overflow-hidden">
        <div className="flex h-full flex-col gap-3 overflow-y-auto pb-16 [scrollbar-width:none]">
          {reportOpen && <ScoutingReportPanel report={scouting} />}
          {!reportOpen && list.length === 0 && (
            <div className="rounded-lg border border-dashed border-line px-[22px] py-5 text-[15px] text-fg-3">
              Insights appear here at key moments and every five minutes.
            </div>
          )}
          {!reportOpen && list.map((i) => {
            const isOpen = open[i.id] ?? i.id === newest;
            const toggle = () => setOpen((o) => ({ ...o, [i.id]: !isOpen }));
            return (
              <div key={i.id} ref={(el) => { refs.current[i.id] = el; }} className={i.id === arrivingId ? 'itg-arrive' : i.type === 'tactics' || i.type === 'substitution' ? 'itg-in' : undefined}>
                {i.type === 'tactics'
                  ? <TacticsCard insight={i} expanded={isOpen} onToggle={toggle} />
                  : i.type === 'substitution'
                    ? <SubstitutionCard insight={i} expanded={isOpen} onToggle={toggle} />
                    : <InsightCard insight={i} mode={mode} expanded={isOpen} onToggle={toggle} />}
              </div>
            );
          })}
        </div>
        <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-b from-transparent to-bg" />
      </div>
    </section>
  );
}
