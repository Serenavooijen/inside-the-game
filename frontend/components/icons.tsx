import type { TeamInfo } from '@/lib/contracts';

export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 30 30" aria-hidden>
      <rect x="1" y="1" width="28" height="28" rx="6" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M15 1v28" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="15" cy="15" r="5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="22" cy="9" r="3" fill="var(--itg-accent)" />
    </svg>
  );
}

/** Generic shield crest, used for the home team. */
export function HomeCrest({ w = 32, h = 36, color = '#2F6BFF', fg = '#FFFFFF' }: { w?: number; h?: number; color?: string; fg?: string }) {
  return (
    <svg width={w} height={h} viewBox="0 0 34 38" aria-hidden>
      <path d="M17 1 32 6v12c0 10-7 16-15 19C9 34 2 28 2 18V6Z" fill={color} stroke={fg} strokeWidth="2" />
      <path d="M7 25q10-13 20 0" fill="none" stroke={fg} strokeWidth="2.5" />
      <path d="M7 25h20M12 25v-5M17 25v-8M22 25v-5" stroke={fg} strokeWidth="1.6" />
    </svg>
  );
}

/** Generic round crest, used for the away team. */
export function AwayCrest({ size = 34, color = '#FFB400', fg = '#121212' }: { size?: number; color?: string; fg?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" aria-hidden>
      <circle cx="18" cy="18" r="16" fill={color} stroke={fg} strokeWidth="2" />
      <circle cx="18" cy="18" r="11" fill="none" stroke={fg} strokeWidth="1.4" />
      <path d="M18 6l3 12-3-3-3 3Z" fill={fg} />
      <path d="M18 30l-3-12 3 3 3-3Z" fill="none" stroke={fg} strokeWidth="1.2" />
    </svg>
  );
}

export function Crest({ team, side, small }: { team: TeamInfo; side: 'home' | 'away'; small?: boolean }) {
  return side === 'home'
    ? <HomeCrest w={small ? 30 : 32} h={small ? 34 : 36} color={team.color} fg={team.fg} />
    : <AwayCrest size={small ? 32 : 34} color={team.color} fg={team.fg} />;
}

export function Ball({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" aria-hidden>
      <circle cx="9" cy="9" r="8.2" fill="#fff" stroke="#121212" strokeWidth="1" />
      <path d="M9 5.2 12.1 7.4 10.9 11H7.1L5.9 7.4Z" fill="#121212" />
      <path d="M9 5.2V1.2M12.1 7.4l3.8-1.2M10.9 11l2.3 3.3M7.1 11l-2.3 3.3M5.9 7.4 2.1 6.2" stroke="#121212" strokeWidth=".9" />
    </svg>
  );
}

export function SmallBall() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden>
      <circle cx="6" cy="6" r="5" fill="#fff" stroke="#121212" />
      <path d="M6 3.5 8.3 5.2 7.4 8H4.6L3.7 5.2Z" fill="#121212" />
    </svg>
  );
}

export function SubIcon({ size = 13 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" strokeWidth="2.5" strokeLinecap="round" aria-hidden>
      <path d="M8 3v14m-4-4 4 4 4-4" stroke="var(--itg-ok)" />
      <path d="M16 21V7m4 4-4-4-4 4" stroke="var(--itg-bad)" />
    </svg>
  );
}

export function Stopwatch({ size = 18, strokeWidth = 2 }: { size?: number; strokeWidth?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" aria-hidden>
      <path d="M10 2h4M12 14l3-3" />
      <circle cx="12" cy="14" r="8" />
    </svg>
  );
}

export function Whistle({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3 11a5 5 0 0 0 9.6 2H21V8H8.2A5 5 0 0 0 3 11Z" />
      <path d="M15 8V5" />
    </svg>
  );
}

export function PlayIcon({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M7 4.5v15a1 1 0 0 0 1.5.86l12-7.5a1 1 0 0 0 0-1.72l-12-7.5A1 1 0 0 0 7 4.5Z" />
    </svg>
  );
}

export function PauseIcon({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <rect x="6" y="4" width="4" height="16" rx="1" />
      <rect x="14" y="4" width="4" height="16" rx="1" />
    </svg>
  );
}

/** Fact-check icon: magnifier with a check mark. */
export function FactCheck({ size = 18, color = 'currentColor' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="10.5" cy="10.5" r="7" />
      <path d="m15.5 15.5 5.5 5.5" />
      <path d="m7.5 10.5 2 2 3.5-4" />
    </svg>
  );
}

export function SunMoon({ day }: { day: boolean }) {
  return day ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}
