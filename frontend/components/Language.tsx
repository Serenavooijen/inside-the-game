'use client';

import { useEffect, useRef, useState } from 'react';
import { LANGS, useLang, type CardView } from '@/lib/i18n';

/** Language for this viewer, next to the theme toggle: a round chip with the code, a small menu EN · NL · ES · FR. */
export function LanguagePicker() {
  const { lang, setLang, t } = useLang();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !box.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', close); };
  }, [open]);
  return (
    <div ref={box} className="relative flex-none">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${t('language')}: ${LANGS.find((l) => l.code === lang)?.name}`}
        title={t('language')}
        className="flex h-9 w-9 items-center justify-center rounded-full border border-line font-mono text-[12px] font-medium uppercase tracking-[.06em] text-fg-2 hover:text-fg"
      >
        {lang}
      </button>
      {open && (
        <div role="menu" aria-label={t('language')} className="itg-in absolute left-0 top-11 z-50 flex flex-col gap-[2px] rounded-md border border-line bg-surface p-1 shadow-[0_12px_32px_rgba(0,0,0,.35)]">
          {LANGS.map((l) => (
            <button
              key={l.code}
              type="button"
              role="menuitemradio"
              aria-checked={lang === l.code}
              lang={l.code}
              onClick={() => { setLang(l.code); setOpen(false); }}
              className={`flex h-9 items-center gap-3 whitespace-nowrap rounded-sm pl-2 pr-4 text-left text-[14px] font-semibold ${lang === l.code ? 'bg-fg text-bg' : 'text-fg-2 hover:bg-surface-2 hover:text-fg'}`}
            >
              <span className="w-6 font-mono text-[12px] font-medium uppercase">{l.code}</span>
              {l.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Small label on a card in another language. "translated · checked": the code compared the translation with
 * the English source (numbers, names, length); a click shows the English original and back. "EN": no checked
 * translation (rejected, too late or still on its way), so the card shows the English text.
 */
export function LangTag({ view, reason, pending, onToggle, compact }: {
  view: CardView; reason?: string; pending?: boolean; onToggle: () => void;
  /** for the commentary bar: "✓ NL" with the full label as tooltip */
  compact?: boolean;
}) {
  const { t, lang } = useLang();
  if (view === 'source') return null;
  if (view === 'english') {
    return (
      <span
        className="flex h-[22px] flex-none items-center rounded-sm border border-line px-[6px] font-mono text-[11px] font-medium tracking-[.08em] text-fg-3"
        title={pending ? t('translating') : `${t('englishOnly')}${reason ? ` (${reason})` : ''}`}
      >
        EN
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={view === 'original'}
      title={`${view === 'translated' ? t('translatedChecked') : t('original')} · ${view === 'original' ? t('showTranslation') : t('showOriginal')}`}
      className="flex h-[22px] flex-none items-center gap-[6px] whitespace-nowrap rounded-sm border border-line bg-transparent px-[6px] font-mono text-[11px] font-medium tracking-[.06em] text-fg-2 hover:border-line-strong hover:text-fg"
    >
      {view === 'translated' && (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--itg-ok)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M20 6 9 17l-5-5" /></svg>
      )}
      {compact ? (view === 'translated' ? lang.toUpperCase() : 'EN') : view === 'translated' ? t('translatedChecked') : t('original')}
    </button>
  );
}
