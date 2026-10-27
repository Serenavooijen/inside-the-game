'use client';

import { useRef } from 'react';
import type { Marker, Speed } from '@/lib/contracts';
import { useLang } from '@/lib/i18n';
import { useTeams } from '@/lib/teams';
import { PauseIcon, PlayIcon, Stopwatch, Whistle } from './icons';

type Props = {
  t: number;
  /** Football minute label for t, e.g. "45+2" */
  minute: string;
  duration: number;
  halftime: number;
  speed: Speed;
  playing: boolean;
  keyMoment: boolean;
  finished: boolean;
  markers: Marker[];
  onToggle: () => void;
  onSpeed: (s: Speed) => void;
  /** t = match second (generator frame) */
  onSeek: (t: number) => void;
};

export function Controls({ t, minute, duration, halftime, speed, playing, keyMoment, finished, markers, onToggle, onSpeed, onSeek }: Props) {
  const teams = useTeams();
  const { t: tr } = useLang();
  const track = useRef<HTMLDivElement>(null);
  const at = (s: number) => Math.min(100, (s / duration) * 100);
  const progress = at(t);
  const ticks = [
    { at: 0, label: "0'" }, { at: at(900), label: "15'" }, { at: at(1800), label: "30'" }, { at: at(halftime), label: tr('ht') },
    { at: at(halftime + 900), label: "60'" }, { at: at(halftime + 1800), label: "75'" }, { at: 100, label: tr('ft') },
  ];

  const seekFromPointer = (clientX: number) => {
    const r = track.current?.getBoundingClientRect();
    if (!r) return;
    const k = Math.max(0, Math.min(1, (clientX - r.left) / r.width));
    onSeek(Math.round(k * duration));
  };

  const speedBtn = (s: Speed) => (
    <button
      type="button"
      onClick={() => onSpeed(s)}
      aria-pressed={speed === s}
      className={`h-10 min-w-[52px] rounded-sm font-display text-[22px] font-extrabold ${speed === s ? 'bg-fg text-bg' : 'bg-transparent text-fg-2 hover:text-fg'}`}
    >
      {s}×
    </button>
  );

  return (
    <footer className="flex h-[112px] flex-none items-center gap-7 border-t border-line bg-bg px-10">
      <button
        type="button"
        onClick={onToggle}
        aria-label={playing ? tr('pause') : tr('play')}
        className="flex h-14 w-14 flex-none items-center justify-center rounded-full bg-fg text-bg active:scale-[.96]"
      >
        {playing ? <PauseIcon /> : <PlayIcon />}
      </button>

      <div className="flex flex-none items-center gap-3">
        <div className="flex items-center gap-1 rounded-md bg-surface-2 p-1" role="group" aria-label={tr('speed')}>
          <div className="flex pl-[6px] pr-2 text-fg-3"><Stopwatch size={18} strokeWidth={1.75} /></div>
          {speedBtn(1)}
          {speedBtn(10)}
        </div>
        {keyMoment && (
          <div className="flex items-center gap-2 text-[14px] font-semibold text-fg-2">
            <Whistle />
            {tr('autoSlowed')}
          </div>
        )}
      </div>

      <div className="relative h-[76px] min-w-0 flex-1">
        {markers.map((m) => (
          <button
            key={`${m.kind}-${m.t}`}
            type="button"
            onClick={() => onSeek(Math.max(0, m.t - 8))}
            title={m.title}
            aria-label={`${m.title}, ${tr('jumpTo', { m: m.minute })}`}
            className="absolute top-0 flex -translate-x-1/2 flex-col items-center gap-1 bg-transparent p-0 text-fg-2 hover:text-fg"
            style={{ left: `${at(m.t)}%` }}
          >
            <div className="flex h-[18px] items-center">
              {m.kind === 'goal' && (
                <span className="box-border inline-block h-4 w-4 rounded-full border-2 border-fg" style={{ background: teams.color(m.team) }} />
              )}
              {m.kind === 'card' && <span className="inline-block h-[15px] w-[11px] rounded-[2px] bg-card-yellow" />}
              {m.kind === 'red' && <span className="inline-block h-[15px] w-[11px] rounded-[2px] bg-card-red" />}
              {m.kind === 'corrected' && <span className="box-border inline-block h-3 w-3 rotate-45 border-2 border-corrected" />}
            </div>
            <div className="font-mono text-[12px]">{m.kind === 'corrected' ? '' : `${m.minute}'`}</div>
          </button>
        ))}
        <div
          ref={track}
          role="slider"
          tabIndex={0}
          aria-label={tr('matchTime')}
          aria-valuemin={0}
          aria-valuemax={duration}
          aria-valuenow={t}
          aria-valuetext={`Minute ${minute}`}
          onPointerDown={(e) => seekFromPointer(e.clientX)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowRight') { e.preventDefault(); onSeek(Math.min(duration, t + 60)); }
            if (e.key === 'ArrowLeft') { e.preventDefault(); onSeek(Math.max(0, t - 60)); }
          }}
          className="absolute left-0 right-0 top-[38px] h-[18px] cursor-pointer"
        >
          <div className="absolute left-0 right-0 top-[6px] h-[6px] rounded-full bg-surface-2">
            <div className="absolute bottom-0 left-0 top-0 rounded-full bg-fg" style={{ width: `${progress}%` }} />
            <div className="absolute top-[-4px] h-[14px] w-[2px] bg-fg-3" style={{ left: `${at(halftime)}%` }} />
            <div
              className="absolute top-1/2 h-[18px] w-[18px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-fg shadow-[0_0_0_4px_var(--itg-bg)]"
              style={{ left: `${progress}%` }}
            />
          </div>
        </div>
        <div className="absolute left-0 right-0 top-[58px] font-mono text-label text-fg-3">
          {ticks.map((k) => (
            <div
              key={k.label}
              className="absolute"
              style={k.at === 0 ? { left: 0 } : k.at === 100 ? { right: 0 } : { left: `${k.at}%`, transform: 'translateX(-50%)' }}
            >
              {k.label}
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-none items-baseline gap-[6px] font-display font-extrabold">
        <div className="text-[40px] leading-none">{finished ? tr('ft') : `${minute}'`}</div>
        {!finished && <div className="text-[20px] text-fg-3">/ 90&apos;</div>}
      </div>
    </footer>
  );
}
