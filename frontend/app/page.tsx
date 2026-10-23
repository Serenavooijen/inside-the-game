'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import type { MatchSummary } from '@/lib/contracts';
import { MATCHES } from '@/lib/matches';
import { API_URL } from '@/lib/useMatchStream';
import { Logo, PlayIcon } from '@/components/icons';
import { ThemeToggle } from '@/components/ThemeToggle';

function Club({ name, short, color, fg }: { name: string; short: string; color: string; fg: string }) {
  return (
    <div className="flex items-center gap-[14px]">
      <div
        className="flex h-9 w-9 items-center justify-center rounded-full font-display text-[15px] font-extrabold shadow-[inset_0_0_0_2px_rgba(255,255,255,.85)]"
        style={{ background: color, color: fg }}
      >
        {short}
      </div>
      <div className="font-display text-[32px] font-bold leading-none">{name}</div>
    </div>
  );
}

export default function PickAMatch() {
  const [matches, setMatches] = useState<MatchSummary[]>(MATCHES);
  useEffect(() => {
    fetch(`${API_URL}/matches`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((m) => { if (Array.isArray(m) && m.length) setMatches(m); })
      .catch(() => { /* keep the built-in list */ });
  }, []);

  return (
    <div className="flex min-h-screen flex-col px-6 md:px-[120px]">
      <header className="flex h-[104px] items-center justify-between border-b border-line">
        <div className="flex items-center gap-[10px]">
          <Logo />
          <span className="font-display text-[28px] font-extrabold uppercase tracking-[.04em]">Inside the Game</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="font-mono text-[13px] tracking-[.12em] text-fg-3">ALL MATCHES ARE SYNTHETIC</span>
          <ThemeToggle />
        </div>
      </header>

      <div className="flex flex-wrap items-end justify-between gap-12 pb-12 pt-[72px]">
        <h1 className="font-display text-[clamp(80px,9vw,160px)] font-extrabold uppercase leading-[.85]">Pick a match</h1>
        <p className="max-w-[520px] pb-3 text-[20px] leading-normal text-fg-2">
          Every match here is generated. Watch it with live stats and AI analysis that is checked against the data.
        </p>
      </div>

      <ul className="flex flex-col border-t border-line">
        {matches.map((m, idx) => {
          const primary = idx === 0 && m.available;
          return (
            <li key={m.id} className="grid grid-cols-[420px_200px_minmax(0,1fr)_180px] items-center gap-12 border-b border-line py-7 max-xl:grid-cols-[minmax(0,1fr)_160px] max-xl:gap-6">
              <div className="flex flex-col gap-3">
                <Club name={m.home.name} short={m.home.short} color={m.home.color} fg={m.home.fg} />
                <Club name={m.away.name} short={m.away.short} color={m.away.color} fg={m.away.fg} />
              </div>
              <div className="flex flex-col gap-[6px]">
                <div className="font-display text-[80px] font-extrabold leading-[.9]">{m.score}</div>
                <div className="font-mono text-[12px] tracking-[.12em] text-fg-3">FULL TIME</div>
              </div>
              <div className="flex flex-col gap-[10px] max-xl:col-span-2">
                <div className="font-serif text-[28px] leading-[1.2] [text-wrap:pretty]">{m.story}</div>
                <div className="font-mono text-[13px] text-fg-3">{m.meta}</div>
              </div>
              <div className="flex flex-col items-end gap-2 max-xl:col-span-2 max-xl:items-start">
                {m.available ? (
                  <>
                    <Link
                      href={`/match/${m.id}`}
                      className={`flex h-[52px] items-center gap-[10px] rounded-md pl-5 pr-6 text-[18px] font-semibold ${primary ? 'border border-accent bg-accent text-[#121212]' : 'border border-line-strong text-fg'}`}
                    >
                      <PlayIcon size={16} /> Watch
                    </Link>
                    <Link href={`/match/${m.id}?replay=1`} className="text-[14px] text-fg-2 underline-offset-4 hover:text-fg hover:underline">
                      Recorded replay
                    </Link>
                  </>
                ) : (
                  <span
                    aria-disabled="true"
                    title="This match has not been generated yet"
                    className="flex h-[52px] cursor-not-allowed items-center gap-[10px] rounded-md border border-line-strong pl-5 pr-6 text-[18px] font-semibold text-fg-3"
                  >
                    <PlayIcon size={16} /> Watch
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      <div className="h-20" />
    </div>
  );
}
