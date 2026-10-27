import type { Insight, SubPlayer, TeamId } from '@/lib/contracts';
import { useCardLanguage, useLang, type Key } from '@/lib/i18n';
import { useTeams } from '@/lib/teams';
import { LangTag } from './Language';
import { Evidence, HeatPitch, LeftOut, Observations, StatusPill } from './TacticsCard';

const KIND: Record<NonNullable<Insight['substitution']>['kind'], Key> = {
  'like-for-like': 'likeForLike', positional: 'positional', 'shape change': 'shapeChange',
};

function SwapIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M7 4v14M3 14l4 4 4-4" /><path d="M17 20V6M13 10l4-4 4 4" />
    </svg>
  );
}

/** Shirt number in the team colours, with name and role; the player going off is dimmed. */
function Chip({ p, team, off }: { p: SubPlayer; team: TeamId; off?: boolean }) {
  const teams = useTeams();
  const { role } = useLang();
  const info = teams.info(team);
  return (
    <div className={`flex min-w-0 items-center gap-2 ${off ? 'opacity-60' : ''}`}>
      <span
        className="flex h-[30px] w-[30px] flex-none items-center justify-center rounded-full font-display text-[16px] font-extrabold leading-none"
        style={{ background: teams.color(team), color: info?.fg ?? 'var(--itg-fg)' }}
        aria-hidden
      >
        {p.n}
      </span>
      <span className="flex min-w-0 flex-col">
        <span className={`truncate text-[15px] font-semibold ${off ? 'line-through decoration-fg-3' : ''}`}>{p.name}</span>
        <span className="truncate font-mono text-label uppercase tracking-[.08em] text-fg-3">{role(p.role)}</span>
      </span>
    </div>
  );
}

type Props = { insight: Insight; expanded?: boolean; onToggle?: () => void };

/** Substitution card: "what to watch" at the moment (code), "impact" about 8 minutes later (Scout). */
export function SubstitutionCard({ insight: i, expanded = false, onToggle }: Props) {
  const teams = useTeams();
  const { t } = useLang();
  const L = useCardLanguage(i);
  const s = i.substitution;
  if (!s) return null;
  const watch = L.tr?.watch ?? s.watch;
  const done = i.phase === 'done';
  const impact = s.stage === 'impact';
  const fallback = i.status === 'fallback';
  const evidence = i.evidence ?? [];
  const border = i.status === 'corrected' && done ? 'border border-corrected' : fallback && done ? 'border border-dashed border-fallback' : 'border border-line';
  return (
    <article className={`box-border flex w-full flex-col gap-[14px] rounded-lg bg-surface px-[22px] py-5 ${border}`}>
      <header className="flex items-center gap-3">
        <div className="flex h-9 w-9 flex-none items-center justify-center rounded-md bg-surface-2 text-fg"><SwapIcon /></div>
        <div className="font-display text-card-type font-extrabold uppercase leading-none tracking-[.05em]">{t('substitution')}</div>
        <div className="flex items-center gap-[6px] font-mono text-[13px] text-fg-2">
          <span className="inline-block h-3 w-3 rounded-[3px]" style={{ background: teams.color(s.team) }} />
          {teams.short(s.team)}
        </div>
        <div className="ml-auto font-display text-[30px] font-extrabold leading-none">{impact ? i.minute : s.minute}&apos;</div>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <span className={`font-mono text-label font-medium uppercase tracking-[.12em] ${impact ? 'text-accent-text' : 'text-fg-2'}`}>
          {impact ? t('impactSince', { m: s.minute }) : t('whatToWatch')}
        </span>
        <span className="rounded-full border border-line px-2 py-[2px] font-mono text-[11px] uppercase tracking-[.08em] text-fg-2">{t(KIND[s.kind])}</span>
      </div>

      <div className="flex flex-col gap-2">
        {s.off.map((p, k) => (
          <div key={p.playerId} className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3">
            <Chip p={p} team={s.team} off />
            <span className="font-mono text-[15px] text-fg-3" aria-label={t('replacedBy')}>→</span>
            {s.on[k] && <Chip p={s.on[k]} team={s.team} />}
          </div>
        ))}
      </div>

      {!done && (
        <div className="flex items-center gap-[10px] font-mono text-[15px] text-accent-text" aria-label="Analysing">
          <span className="itg-pulse inline-block h-[10px] w-[10px] rounded-full bg-accent" />
          {t('readingChange')}
        </div>
      )}

      {done && !impact && watch.length > 0 && (
        <ul key={L.view} lang={L.textLang} className={`flex flex-col gap-2 ${L.view !== 'source' ? 'itg-fade' : ''}`}>
          {watch.map((w) => (
            <li key={w} className="flex gap-[10px] font-serif text-[20px] leading-[1.25] text-fg [text-wrap:pretty]">
              <span className="mt-[10px] h-[6px] w-[6px] flex-none rounded-full bg-fg-3" />
              {w}
            </li>
          ))}
        </ul>
      )}

      {done && impact && (
        <>
          <Observations observations={i.observations ?? []} translated={L.tr?.observations} lang={L.textLang} />
          {s.heatmaps.length === 2 && (
            <div className="grid grid-cols-2 gap-3">
              {s.heatmaps.map((h, k) => <HeatPitch key={k} heatmap={h} width="100%" caption={s.heatmapLabels[k]} />)}
            </div>
          )}
        </>
      )}

      {done && (i.rejectedClaims?.length ?? 0) > 0 && <LeftOut items={i.rejectedClaims ?? []} />}

      {done && (
        <footer className="flex flex-wrap items-center gap-3">
          <StatusPill status={i.status} reason={i.fallbackReason} />
          <LangTag view={L.view} reason={L.reason} pending={L.pending} onToggle={L.toggle} />
          {onToggle && evidence.length > 0 && (
            <button
              type="button"
              onClick={onToggle}
              aria-expanded={expanded}
              className="ml-auto flex flex-none items-center gap-[6px] whitespace-nowrap rounded-full border border-line bg-transparent px-3 py-[5px] text-[14px] font-medium text-fg-2 hover:text-fg"
            >
              {t('evidence')} · {evidence.length}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ transform: expanded ? 'rotate(180deg)' : 'none' }} aria-hidden><path d="m6 9 6 6 6-6" /></svg>
            </button>
          )}
        </footer>
      )}
      {done && expanded && evidence.length > 0 && <Evidence items={evidence} />}
    </article>
  );
}
