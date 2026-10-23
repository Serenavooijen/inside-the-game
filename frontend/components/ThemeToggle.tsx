'use client';

import { useEffect, useState } from 'react';
import { SunMoon } from './icons';

/** Switches between the night (default) and day theme on <html>. */
export function ThemeToggle() {
  const [day, setDay] = useState(false);
  useEffect(() => { setDay(document.documentElement.classList.contains('theme-day')); }, []);
  const toggle = () => {
    const next = !day;
    setDay(next);
    const el = document.documentElement;
    el.classList.toggle('theme-day', next);
    el.classList.toggle('theme-night', !next);
    try { localStorage.setItem('itg-theme', next ? 'day' : 'night'); } catch { /* storage blocked */ }
  };
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={day ? 'Switch to night theme' : 'Switch to day theme'}
      title={day ? 'Night theme' : 'Day theme'}
      className="flex h-9 w-9 items-center justify-center rounded-full border border-line text-fg-2 hover:text-fg"
    >
      <SunMoon day={day} />
    </button>
  );
}
