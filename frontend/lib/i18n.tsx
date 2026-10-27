'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Translation } from './contracts';
import { DICTS, ROLES, STORAGE_KEY, cardView, ordinals, translator, type Lang, type T } from './dictionary';

export { LANGS, cardView, cornerOutcome, translator } from './dictionary';
export type { CardView, Key, Lang, T } from './dictionary';

/** The viewer's language: context, the saved choice and the hooks the components use. */
type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: T; ordinal: (n: number) => string; role: (name: string) => string };

const LangContext = createContext<Ctx>({
  lang: 'en', setLang: () => {}, t: translator('en'), ordinal: ordinals.en, role: (n) => n,
});

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, set] = useState<Lang>('en');
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as Lang | null;
      if (saved && saved in DICTS) set(saved);
    } catch { /* storage blocked: English */ }
  }, []);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  const setLang = useCallback((l: Lang) => {
    set(l);
    try { localStorage.setItem(STORAGE_KEY, l); } catch { /* storage blocked */ }
  }, []);
  const value = useMemo<Ctx>(() => ({
    lang, setLang, t: translator(lang), ordinal: ordinals[lang],
    role: (name: string) => (lang === 'en' ? name : ROLES[lang][name] ?? name),
  }), [lang, setLang]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export const useLang = () => useContext(LangContext);

export function useCardLanguage(item: { phase?: string; translations?: Record<string, Translation> }) {
  const { lang } = useLang();
  const [original, setOriginal] = useState(false);
  const view = cardView(lang, item, original);
  const tr = view === 'translated' ? item.translations![lang] : undefined;
  return {
    view, tr, lang,
    /** BCP 47 tag of the text shown, for the `lang` attribute */
    textLang: tr ? lang : 'en',
    reason: item.translations?.[lang]?.reason,
    pending: view === 'english' && !item.translations?.[lang],
    toggle: () => setOriginal((o) => !o),
  };
}
