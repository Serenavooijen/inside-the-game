'use client';

import { useEffect, useRef, useState } from 'react';
import type { Insight } from '@/lib/contracts';
import { InsightCard } from './InsightCard';

type Props = {
  insights: Insight[];
  mode: 'casual' | 'analyst';
  onMode: (m: 'casual' | 'analyst') => void;
  /** id of the card that just arrived from the hero (animates in) */
  arrivingId?: string | null;
  /** "<insight id>:<nonce>" scrolls that card into view (e.g. from the fact-check pill) */
  focusId?: string | null;
};

/** Smart lane: newest first, newest card open. */
export function ProducerFeed({ insights, mode, onMode, arrivingId, focusId }: Props) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const refs = useRef<Record<string, HTMLDivElement | null>>({});
  const list = [...insights].sort((a, b) => b.t - a.t).slice(0, 14);
  const newest = list[0]?.id;

  useEffect(() => {
    if (!focusId) return;
    const id = focusId.split(':')[0];
    setOpen((o) => ({ ...o, [id]: true }));
    refs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [focusId]);

  const seg = (m: 'casual' | 'analyst', label: string) => (
    <button
      type="button"
      onClick={() => onMode(m)}
      aria-pressed={mode === m}
      className={`h-[34px] rounded-sm px-3 text-[14px] font-semibold ${mode === m ? 'bg-fg text-bg' : 'bg-transparent text-fg-2 hover:text-fg'}`}
    >
      {label}
    </button>
  );

  return (
    <section className="flex min-w-[400px] flex-1 flex-col gap-4" aria-label="Producer feed">
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-col gap-[2px]">
          <h2 className="font-display text-[28px] font-extrabold uppercase leading-none tracking-[.04em]">Producer feed</h2>
          <div className="font-mono text-label tracking-[.12em] text-fg-3">NEWEST FIRST</div>
        </div>
        <div className="flex gap-[2px] rounded-md bg-surface-2 p-[3px]" role="group" aria-label="Explanation style">
          {seg('casual', 'Casual fan')}
          {seg('analyst', 'Analyst')}
        </div>
      </div>
      <div className="relative min-h-0 flex-1 overflow-hidden">
        <div className="flex h-full flex-col gap-3 overflow-y-auto pb-16 [scrollbar-width:none]">
          {list.length === 0 && (
            <div className="rounded-lg border border-dashed border-line px-[22px] py-5 text-[15px] text-fg-3">
              Insights appear here at key moments and every five minutes.
            </div>
          )}
          {list.map((i) => {
            const isOpen = open[i.id] ?? i.id === newest;
            return (
              <div key={i.id} ref={(el) => { refs.current[i.id] = el; }} className={i.id === arrivingId ? 'itg-arrive' : undefined}>
                <InsightCard
                  insight={i}
                  mode={mode}
                  expanded={isOpen}
                  onToggle={() => setOpen((o) => ({ ...o, [i.id]: !isOpen }))}
                />
              </div>
            );
          })}
        </div>
        <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-b from-transparent to-bg" />
      </div>
    </section>
  );
}
