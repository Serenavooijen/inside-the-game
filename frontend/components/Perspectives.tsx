'use client';

import { useState } from 'react';
import type { Insight, Perspective } from '@/lib/contracts';
import { useLang } from '@/lib/i18n';
import { usePreferences } from '@/lib/preferences';
import { perspectiveFor } from '@/lib/prefs';
import { useTeams } from '@/lib/teams';
import { LangTag } from './Language';
import { Swatch } from './ProfileMenu';
import { Segmented } from './Segmented';

/** The checked variant for the viewer's club, or null (neutral card). */
export function usePerspective(perspectives: Insight['perspectives']): Perspective | null {
  const { prefs } = usePreferences();
  return perspectiveFor(perspectives, prefs);
}

/** "{club} view | Neutral" on the card: shown whenever a checked variant for your club exists (Analyst mode). */
export function PerspectiveSwitch({ perspectives }: { perspectives: Insight['perspectives'] }) {
  const teams = useTeams();
  const { t } = useLang();
  const { prefs, set } = usePreferences();
  const available = perspectiveFor(perspectives, { ...prefs, tacticsView: 'club' });
  if (!available || prefs.club === 'neutral') return null;
  return (
    <Segmented
      label={t('tacticsView')}
      size="sm"
      value={prefs.tacticsView}
      onChange={(v) => set({ tacticsView: v })}
      options={[
        { value: 'club', label: <><Swatch team={prefs.club} />{t('clubView', { club: teams.label(prefs.club) })}</> },
        { value: 'neutral', label: t('neutral') },
      ]}
    />
  );
}

const Label = ({ children }: { children: string }) => (
  <span className="mr-2 font-mono text-label uppercase tracking-[.12em] text-fg-3">{children}</span>
);

/** "How to beat {opponent}" and "What {opponent} changed today": the card from your club's side. */
export function PerspectiveView({ p, translations }: { p: Perspective; translations?: Insight['translations'] }) {
  const teams = useTeams();
  const { t, lang } = useLang();
  const { prefs, opponentOf } = usePreferences();
  const [open, setOpen] = useState(0);
  const [original, setOriginal] = useState(false);
  const club = prefs.club;
  const opp = opponentOf(club);
  const tr = lang !== 'en' ? translations?.[lang]?.perspectives?.[club] : undefined;
  const view = lang === 'en' ? 'source' : tr ? (original ? 'original' : 'translated') : 'english';
  const shown = view === 'translated' ? tr : undefined;

  return (
    <div className="flex flex-col gap-4" lang={shown ? lang : 'en'}>
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3 border-b-2 pb-2" style={{ borderColor: teams.color(club) }}>
          <div className="font-display text-[20px] font-extrabold uppercase leading-none tracking-[.05em]">{t('howToBeat', { team: teams.label(opp) })}</div>
          <LangTag view={view} onToggle={() => setOriginal((o) => !o)} pending={false} />
        </div>
        <ol className="flex flex-col">
          {p.levers.map((lv, k) => {
            const x = shown?.levers[k];
            const isOpen = open === k;
            return (
              <li key={k} className="flex flex-col border-b border-line last:border-b-0">
                <button
                  type="button"
                  onClick={() => setOpen(isOpen ? -1 : k)}
                  aria-expanded={isOpen}
                  className="flex min-h-11 w-full items-start gap-3 bg-transparent py-[10px] text-left"
                >
                  <span className="mt-[3px] flex-none font-mono text-label uppercase tracking-[.12em] text-fg-3">{k + 1}</span>
                  <span className={`min-w-0 flex-1 font-serif text-[19px] leading-[1.25] text-fg [text-wrap:pretty] ${isOpen ? '' : 'line-clamp-1'}`}>
                    {x?.observation ?? lv.observation}
                  </span>
                  <svg className="mt-[6px] flex-none text-fg-3" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ transform: isOpen ? 'rotate(180deg)' : 'none' }} aria-hidden><path d="m6 9 6 6 6-6" /></svg>
                </button>
                {isOpen && (
                  <div className="itg-fade mb-3 ml-7 flex flex-col gap-[6px] border-l-2 border-line pl-3">
                    <div className="text-[15px] leading-[1.35] text-fg-2"><Label>{t('consequence')}</Label>{x?.consequence ?? lv.consequence}</div>
                    <div className="text-[15px] leading-[1.35] text-fg-2"><Label>{t('forCoach')}</Label>{x?.coachAction ?? lv.coachAction}</div>
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      </div>

      {p.changes.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="font-mono text-label uppercase tracking-[.12em] text-fg-3">{t('changedToday', { team: teams.label(opp) })}</div>
          {p.changes.map((c, k) => (
            <div key={k} className="flex items-start justify-between gap-3 text-[14px] leading-[1.35] text-fg-2">
              <span className="min-w-0">{shown?.changes[k] ?? c.text}</span>
              <span className={`flex-none rounded-full border px-2 py-[2px] font-mono text-[11px] uppercase tracking-[.08em] ${c.label === 'changed' ? 'border-accent text-accent-text' : 'border-line text-fg-3'}`}>
                {c.label === 'changed' ? t('changedLabel') : t('sameLabel')}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
