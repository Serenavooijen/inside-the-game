import type { Insight, TeamId, Zone } from '@/lib/contracts';
import { FactCheck, Stopwatch } from './icons';

type Props = {
  insight: Insight;
  size?: 'feed' | 'hero';
  mode?: 'casual' | 'analyst';
  expanded?: boolean;
  onToggle?: () => void;
};

const LABELS: Record<Insight['type'], string> = {
  goal: 'Goal', bigchance: 'Big chance', card: 'Card', momentum: 'Momentum', update: '5-min update', fulltime: 'Full time',
};


const teamText = (t?: TeamId) => (t === 'kba' ? 'var(--itg-kba-text)' : t === 'ngr' ? 'var(--itg-ngr-text)' : 'var(--itg-fg)');

function TypeIcon({ type, card }: { type: Insight['type']; card?: Insight['card'] }) {
  const common = { width: 22, height: 22, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round' as const, 'aria-hidden': true };
  if (type === 'goal') return (
    <svg {...common}><path d="M2 20V5h20v15" /><path d="M2 9h20M2 13h20M7 5v15M12 5v15M17 5v15" strokeOpacity=".35" /><circle cx="15" cy="16" r="4" fill="#fff" stroke="#121212" /></svg>
  );
  if (type === 'bigchance') return (
    <svg {...common}><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4" /><path d="M12 1v4M12 19v4M1 12h4M19 12h4" /></svg>
  );
  if (type === 'card') return <span className={`inline-block h-[19px] w-[14px] rotate-[8deg] rounded-[3px] ${card === 'red' ? 'bg-card-red' : 'bg-card-yellow'}`} />;
  if (type === 'momentum') return (
    <svg {...common} strokeLinejoin="round"><path d="M22 7 13.5 15.5 8.5 10.5 2 17" /><path d="M16 7h6v6" /></svg>
  );
  return <Stopwatch size={22} strokeWidth={1.5} />;
}

function MiniPitch({ zone: z, width }: { zone: Zone; width: number }) {
  const dir = z.dir ?? 1;
  return (
    <div className="flex flex-none flex-col gap-[6px]" style={{ width }}>
      <svg viewBox="-3 -3 111 74" className="block w-full rounded-md" style={{ background: 'var(--itg-grass-a)' }} aria-label={z.label}>
        <rect x={z.x} y={z.y} width={z.w} height={z.h} fill="#D4FF3F" fillOpacity=".42" stroke="#D4FF3F" strokeWidth=".8" />
        <g fill="none" stroke="#fff" strokeOpacity=".75" strokeWidth=".7">
          <rect x="0" y="0" width="105" height="68" />
          <line x1="52.5" y1="0" x2="52.5" y2="68" />
          <circle cx="52.5" cy="34" r="9.15" />
          <rect x="0" y="13.84" width="16.5" height="40.32" />
          <rect x="88.5" y="13.84" width="16.5" height="40.32" />
        </g>
        {z.line !== undefined && <line x1={z.line} y1="-2" x2={z.line} y2="70" stroke="#fff" strokeWidth="1" strokeDasharray="2 1.5" />}
        <path
          d={dir === 1 ? 'M40 60 L100 60 M94 55 L100 60 L94 65' : 'M65 60 L5 60 M11 55 L5 60 L11 65'}
          fill="none" stroke="#fff" strokeWidth="1.2" strokeOpacity=".6"
        />
      </svg>
      <div className="font-mono text-label text-fg-3">{z.label}</div>
    </div>
  );
}

export function InsightCard({ insight: i, size = 'feed', mode = 'casual', expanded = false, onToggle }: Props) {
  const hero = size === 'hero';
  const done = i.phase === 'done';
  const corrected = i.status === 'corrected' && done;
  const fallback = i.status === 'fallback';
  const evidence = i.evidence ?? [];
  const textSize = hero ? 'text-insight-hero' : 'text-insight';
  const showPitch = !!i.zone && done && (hero || expanded) && !corrected;

  const border = corrected ? 'border border-corrected' : fallback && done ? 'border border-dashed border-fallback' : 'border border-line';

  return (
    <article
      className={`box-border flex w-full flex-col gap-[14px] rounded-lg bg-surface ${border} ${hero ? 'px-8 py-7 shadow-[0_24px_64px_rgba(0,0,0,.45),0_8px_16px_rgba(0,0,0,.25)]' : 'px-[22px] py-5'}`}
      aria-live={hero ? 'polite' : undefined}
    >
      <header className="flex items-center gap-3">
        <div className="flex h-9 w-9 flex-none items-center justify-center rounded-md bg-surface-2 text-fg"><TypeIcon type={i.type} card={i.card} /></div>
        <div className={`font-display font-extrabold uppercase leading-none tracking-[.05em] ${hero ? 'text-[28px]' : 'text-card-type'}`}>{i.type === 'card' && i.card === 'red' ? 'Red card' : LABELS[i.type]}</div>
        {i.team && (
          <div className="flex items-center gap-[6px] font-mono text-[13px] text-fg-2">
            <span className="inline-block h-3 w-3 rounded-[3px]" style={{ background: i.team === 'kba' ? 'var(--itg-kba)' : 'var(--itg-ngr)' }} />
            {i.team.toUpperCase()}
          </div>
        )}
        <div className={`ml-auto font-display font-extrabold leading-none ${hero ? 'text-[40px]' : 'text-[30px]'}`}>{i.minute}&apos;</div>
      </header>

      <div className={`flex items-center gap-2 font-mono text-label font-medium uppercase tracking-[.12em] ${fallback ? 'text-fallback' : 'text-accent-text'}`}>
        <span className="inline-block h-2 w-2 rounded-[2px]" style={{ background: fallback ? 'var(--itg-fallback)' : 'var(--itg-accent)' }} />
        {fallback ? 'Template text' : 'AI analysis'}
      </div>

      {i.phase === 'analysing' && (
        <div className="flex flex-col gap-3" aria-label="Analysing">
          <div className="flex items-center gap-[10px] font-mono text-[15px] text-accent-text">
            <span className="itg-pulse inline-block h-[10px] w-[10px] rounded-full bg-accent" />
            Analysing…
          </div>
          <div className="h-[14px] w-[92%] rounded-sm bg-surface-2" />
          <div className="h-[14px] w-[64%] rounded-sm bg-surface-2" />
        </div>
      )}

      {corrected && (
        <div className="flex flex-col gap-[14px]">
          <div className="flex items-center gap-[10px] rounded-md bg-corrected-soft px-[14px] py-[10px] text-corrected">
            <FactCheck size={22} />
            <div className="font-display text-[22px] font-extrabold uppercase leading-none tracking-[.08em]">Corrected</div>
            <div className="ml-auto whitespace-nowrap font-mono text-[12px]">Checked against event data</div>
          </div>
          <div className="text-[15px] text-fg-3 line-through">AI draft: {i.claim}</div>
          <div className={`font-serif ${textSize} [text-wrap:pretty]`}>{i.text}</div>
          {i.stats && (
            <div className="flex items-end gap-5">
              <div className="flex flex-col gap-1">
                <div className="font-display text-[64px] font-extrabold leading-[.9]" style={{ color: teamText(i.stats.aTeam) }}>{i.stats.a}</div>
                <div className="whitespace-nowrap font-mono text-[12px] text-fg-2">{i.stats.aLabel}</div>
              </div>
              <div className="pb-[22px] font-display text-[28px] font-bold text-fg-3">vs</div>
              <div className="flex flex-col gap-1">
                <div className="font-display text-[64px] font-extrabold leading-[.9]" style={{ color: teamText(i.stats.bTeam) }}>{i.stats.b}</div>
                <div className="whitespace-nowrap font-mono text-[12px] text-fg-2">{i.stats.bLabel}</div>
              </div>
            </div>
          )}
        </div>
      )}

      {!corrected && i.phase !== 'analysing' && (
        <div className="flex items-start gap-5">
          <p className={`min-w-0 flex-1 font-serif ${textSize} text-fg [text-wrap:pretty]`}>
            {i.text}
            {i.phase === 'streaming' && (
              <span className="itg-blink ml-1 inline-block h-[0.85em] w-[0.45em] bg-accent align-[-0.08em]" aria-hidden />
            )}
          </p>
          {showPitch && <MiniPitch zone={i.zone!} width={hero ? 220 : 150} />}
        </div>
      )}

      {mode === 'analyst' && done && !corrected && i.analystStats && i.analystStats.length > 0 && (
        <div className="grid grid-cols-3 gap-px overflow-hidden rounded-md border border-line bg-line">
          {i.analystStats.map((s) => (
            <div key={s.k} className="flex flex-col gap-[2px] bg-surface px-3 py-[10px]">
              <div className="font-display text-[26px] font-bold leading-none">{s.v}</div>
              <div className="font-mono text-label text-fg-3">{s.k}</div>
            </div>
          ))}
        </div>
      )}

      {done && (
        <footer className="flex flex-wrap items-center gap-3">
          {i.status === 'checked' && (
            <div className="flex items-center gap-[6px] rounded-full bg-checked-soft py-[5px] pl-2 pr-[10px] text-[14px] font-semibold text-checked">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M20 6 9 17l-5-5" /></svg>
              Checked
            </div>
          )}
          {corrected && (
            <div className="flex items-center gap-[6px] rounded-full bg-corrected-soft py-[5px] pl-2 pr-[10px] text-[14px] font-semibold text-corrected">
              <FactCheck size={16} />
              Corrected
            </div>
          )}
          {fallback && (
            <div className="flex items-center gap-2">
              <div className="rounded-full border border-dashed border-fallback px-[10px] py-[5px] text-[14px] font-semibold text-fallback">Fallback</div>
              <div className="font-mono text-[12px] text-fg-3">{i.fallbackReason ?? 'Model timed out · template used'}</div>
            </div>
          )}
          {evidence.length > 0 && onToggle && (
            <button
              type="button"
              onClick={onToggle}
              aria-expanded={expanded}
              className="ml-auto flex flex-none items-center gap-[6px] whitespace-nowrap rounded-full border border-line bg-transparent px-3 py-[5px] text-[14px] font-medium text-fg-2 hover:text-fg"
            >
              Evidence · {evidence.length}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ transform: expanded ? 'rotate(180deg)' : 'none' }} aria-hidden><path d="m6 9 6 6 6-6" /></svg>
            </button>
          )}
        </footer>
      )}

      {done && (expanded || (hero && !onToggle)) && evidence.length > 0 && (
        <ul className="flex flex-col border-t border-line">
          {evidence.map((e) => (
            <li key={e} className="flex items-center gap-[10px] border-b border-line py-[9px] font-mono text-evidence text-fg">
              <span className="h-[6px] w-[6px] flex-none rounded-full bg-fg-3" />
              {e}
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
