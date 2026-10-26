import type { Fact, Heatmap, Insight, Player, ScoutingReport, TacticalObservation } from '@/lib/contracts';
import { useTeams } from '@/lib/teams';
import { AttackArrow, PitchMarkings } from './InsightCard';
import { FactCheck } from './icons';

const TRIGGER: Record<NonNullable<Insight['trigger']>, string> = {
  interval: 'Every 5 minutes', half_time: 'Half time', substitution: 'After the substitution', scouting: 'Cup match',
};

const NO_CHANGE = 'No tactical change';

const COMPARE: Record<TacticalObservation['compareToCup'], string | null> = {
  same: 'As in the cup', changed: 'Changed since the cup', 'n/a': null,
};

export function TacticsIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="2.5" y="4" width="19" height="16" rx="1.5" />
      <path d="M12 4v16" strokeOpacity=".35" />
      <circle cx="7" cy="9" r="1.4" /><circle cx="7" cy="15" r="1.4" />
      <path d="M15 8.5l3 3m0-3l-3 3" /><path d="M9 12h4.5" strokeDasharray="1.5 1.5" /><path d="m13 10.5 1.5 1.5-1.5 1.5" />
    </svg>
  );
}

/** Heatmap of the window plus the mean build-up positions (shows where the 6 stands). */
export function HeatPitch({ heatmap, buildUp, width, caption }: { heatmap?: Heatmap; buildUp?: Player[]; width: number | string; caption?: string }) {
  const teams = useTeams();
  if (!heatmap && !buildUp?.length) return null;
  const cols = heatmap?.grid[0]?.length ?? 6;
  const rows = heatmap?.grid.length ?? 4;
  const max = Math.max(1, ...(heatmap?.grid.flat() ?? [1]));
  const team = heatmap?.team ?? buildUp?.[0]?.team;
  const label = caption ?? [heatmap && 'Presence', buildUp?.length && 'mean build-up positions'].filter(Boolean).join(' · ');
  return (
    <div className="flex flex-none flex-col gap-[6px]" style={{ width }}>
      <svg viewBox="-3 -3 111 74" className="block w-full rounded-md" style={{ background: 'var(--itg-grass-a)' }} aria-label={label}>
        {heatmap?.grid.map((row, r) => row.map((v, c) => (
          <rect key={`${r}-${c}`} x={(c * 105) / cols} y={(r * 68) / rows} width={105 / cols} height={68 / rows}
            fill="#D4FF3F" fillOpacity={(0.55 * v) / max} />
        )))}
        <PitchMarkings />
        {buildUp?.map((p) => (
          <g key={p.id}>
            <circle cx={p.x} cy={p.y} r="2.6" fill={teams.color(p.team)} stroke="#fff" strokeWidth=".5" />
            <text x={p.x} y={p.y + 1.1} textAnchor="middle" fontSize="3" fontWeight="700" fill="#fff">{p.n}</text>
          </g>
        ))}
        {heatmap && <AttackArrow dir={heatmap.dir} />}
      </svg>
      <div className="flex min-w-0 items-center gap-[6px] font-mono text-label text-fg-3">
        {team && <span className="inline-block h-[10px] w-[10px] rounded-[2px]" style={{ background: teams.color(team) }} />}
        <span className="truncate" title={label}>{label}</span>
      </div>
    </div>
  );
}

/** Observation, then (set apart) the consequence and what a coach would do. */
export function Observations({ observations }: { observations: TacticalObservation[] }) {
  const teams = useTeams();
  return (
    <ol className="flex flex-col gap-4">
      {observations.map((o, k) => {
        const cmp = COMPARE[o.compareToCup];
        return (
          <li key={k} className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              {o.team && (
                <span className="flex items-center gap-[6px] font-mono text-[12px] text-fg-2">
                  <span className="inline-block h-[10px] w-[10px] rounded-[2px]" style={{ background: teams.color(o.team) }} />
                  {teams.info(o.team)?.short ?? o.team.toUpperCase()}
                </span>
              )}
              {cmp && (
                <span className={`rounded-full border px-2 py-[2px] font-mono text-[11px] uppercase tracking-[.08em] ${o.compareToCup === 'changed' ? 'border-accent text-accent-text' : 'border-line text-fg-3'}`}>
                  {cmp}
                </span>
              )}
            </div>
            <p className="font-serif text-[21px] leading-[1.25] text-fg [text-wrap:pretty]">{o.observation}</p>
            <div className="flex flex-col gap-[6px] border-l-2 border-line pl-3">
              <div className="text-[15px] leading-[1.35] text-fg-2">
                <span className="mr-2 font-mono text-label uppercase tracking-[.12em] text-fg-3">Consequence</span>
                {o.consequence}
              </div>
              {o.coachAction && (
                <div className="text-[15px] leading-[1.35] text-fg-2">
                  <span className="mr-2 font-mono text-label uppercase tracking-[.12em] text-fg-3">For the coach</span>
                  {o.coachAction}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function LeftOut({ items }: { items: { text: string; reason: string }[] }) {
  if (!items.length) return null;
  return (
    <div className="flex flex-col gap-2 rounded-md bg-corrected-soft px-[14px] py-[10px]">
      <div className="flex items-center gap-2 text-corrected">
        <FactCheck size={18} />
        <span className="font-mono text-label font-medium uppercase tracking-[.12em]">Not verifiable · left out</span>
      </div>
      {items.map((r, k) => (
        <div key={k} className="flex flex-col gap-[2px]">
          <div className="text-[14px] text-fg-3 line-through">{r.text}</div>
          <div className="font-mono text-[12px] text-fg-3">{r.reason}</div>
        </div>
      ))}
    </div>
  );
}

export function StatusPill({ status, reason }: { status: Insight['status']; reason?: string }) {
  if (status === 'checked') return (
    <div className="flex items-center gap-[6px] rounded-full bg-checked-soft py-[5px] pl-2 pr-[10px] text-[14px] font-semibold text-checked">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M20 6 9 17l-5-5" /></svg>
      Checked
    </div>
  );
  if (status === 'corrected') return (
    <div className="flex items-center gap-[6px] rounded-full bg-corrected-soft py-[5px] pl-2 pr-[10px] text-[14px] font-semibold text-corrected">
      <FactCheck size={16} />
      Corrected
    </div>
  );
  return (
    <div className="flex items-center gap-2">
      <div className="rounded-full border border-dashed border-fallback px-[10px] py-[5px] text-[14px] font-semibold text-fallback">Fallback</div>
      <div className="font-mono text-[12px] text-fg-3">{reason ?? 'Scout unavailable · facts and playbook used'}</div>
    </div>
  );
}

export function Evidence({ items }: { items: string[] }) {
  return (
    <ul className="flex flex-col border-t border-line">
      {items.map((e) => (
        <li key={e} className="flex items-center gap-[10px] border-b border-line py-[9px] font-mono text-evidence text-fg">
          <span className="h-[6px] w-[6px] flex-none rounded-full bg-fg-3" />
          {e}
        </li>
      ))}
    </ul>
  );
}

type Props = { insight: Insight; expanded?: boolean; onToggle?: () => void };

/** The Scout's tactical card in the producer feed (Analyst mode). */
export function TacticsCard({ insight: i, expanded = false, onToggle }: Props) {
  const done = i.phase === 'done';
  const fallback = i.status === 'fallback';
  const scouting = i.trigger === 'scouting';
  /** Status card made by the code when the Scout had nothing new (backend: scout.NO_CHANGE) */
  const noChange = i.text === NO_CHANGE;
  const evidence = i.evidence ?? [];
  const border = i.status === 'corrected' && done ? 'border border-corrected' : fallback && done ? 'border border-dashed border-fallback' : 'border border-line';
  return (
    <article className={`box-border flex w-full flex-col gap-[14px] rounded-lg bg-surface px-[22px] py-5 ${border}`}>
      <header className="flex items-center gap-3">
        <div className="flex h-9 w-9 flex-none items-center justify-center rounded-md bg-surface-2 text-fg"><TacticsIcon /></div>
        <div className="font-display text-card-type font-extrabold uppercase leading-none tracking-[.05em]">{scouting ? 'Scouting report (cup)' : 'Tactics'}</div>
        {i.window && !scouting && <div className="font-mono text-[13px] text-fg-2">{i.window.label}</div>}
        <div className="ml-auto font-display text-[30px] font-extrabold leading-none">{scouting ? 'KO' : `${i.minute}'`}</div>
      </header>

      <div className={`flex items-center gap-2 font-mono text-label font-medium uppercase tracking-[.12em] ${fallback ? 'text-fallback' : 'text-accent-text'}`}>
        <span className="inline-block h-2 w-2 rounded-[2px]" style={{ background: fallback ? 'var(--itg-fallback)' : 'var(--itg-accent)' }} />
        {fallback ? 'Facts + playbook' : noChange ? 'Measured by the code' : 'Scout · AI analysis'}
        {i.trigger && <span className="text-fg-3">· {TRIGGER[i.trigger]}</span>}
      </div>

      {!done && (
        <div className="flex flex-col gap-3" aria-label="Analysing">
          <div className="flex items-center gap-[10px] font-mono text-[15px] text-accent-text">
            <span className="itg-pulse inline-block h-[10px] w-[10px] rounded-full bg-accent" />
            Reading the shape…
          </div>
          <div className="h-[14px] w-[92%] rounded-sm bg-surface-2" />
          <div className="h-[14px] w-[64%] rounded-sm bg-surface-2" />
        </div>
      )}

      {done && (
        <>
          {noChange && <div className="font-display text-[22px] font-extrabold uppercase tracking-[.06em] text-fg-2">No tactical change</div>}
          <Observations observations={i.observations ?? []} />
          <HeatPitch heatmap={i.heatmap} buildUp={i.buildUp} width={300} />
          {(i.rejectedClaims?.length ?? 0) > 0 && <LeftOut items={i.rejectedClaims ?? []} />}
          <footer className="flex flex-wrap items-center gap-3">
            <StatusPill status={i.status} reason={i.fallbackReason} />
            {onToggle && evidence.length > 0 && (
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
          {expanded && evidence.length > 0 && <Evidence items={evidence} />}
        </>
      )}
    </article>
  );
}

/** "Scouting report (cup)": the Scout's report on the previous meeting, made before kick-off. */
export function ScoutingReportPanel({ report }: { report: ScoutingReport }) {
  const cited = new Set(report.observations.flatMap((o) => o.factIds));
  const facts: Fact[] = report.facts.filter((f) => cited.has(f.factId));
  return (
    <article className="box-border flex w-full flex-col gap-[14px] rounded-lg border border-line bg-surface px-[22px] py-5">
      <header className="flex items-center gap-3">
        <div className="flex h-9 w-9 flex-none items-center justify-center rounded-md bg-surface-2 text-fg"><TacticsIcon /></div>
        <div className="flex flex-col gap-[2px]">
          <div className="font-display text-card-type font-extrabold uppercase leading-none tracking-[.05em]">Scouting report</div>
          <div className="font-mono text-[13px] text-fg-2">{report.title}</div>
        </div>
      </header>
      <div className="font-mono text-label font-medium uppercase tracking-[.12em] text-accent-text">
        Made before kick-off · baseline for every tactics card
      </div>
      <Observations observations={report.observations} />
      {report.heatmaps.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {report.heatmaps.map((h) => <HeatPitch key={h.team} heatmap={h} width={170} />)}
        </div>
      )}
      {report.status === 'corrected' && <LeftOut items={report.rejectedClaims} />}
      <footer className="flex flex-wrap items-center gap-3">
        <StatusPill status={report.status} />
        {report.generatedBy && <div className="font-mono text-[12px] text-fg-3">by {report.generatedBy}</div>}
      </footer>
      {facts.length > 0 && <Evidence items={facts.map((f) => f.text)} />}
    </article>
  );
}
