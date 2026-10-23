import type { Config } from 'tailwindcss';

const v = (n: string) => `var(--itg-${n})`;

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: v('bg'),
        surface: v('surface'),
        'surface-2': v('surface-2'),
        line: v('line'),
        'line-strong': v('line-strong'),
        fg: v('fg'),
        'fg-2': v('fg-2'),
        'fg-3': v('fg-3'),
        accent: v('accent'),
        'accent-text': v('accent-text'),
        checked: v('ok'),
        'checked-soft': v('ok-soft'),
        corrected: v('bad'),
        'corrected-soft': v('bad-soft'),
        fallback: v('fallback'),
        grass: { a: v('grass-a'), b: v('grass-b') },
        kba: { DEFAULT: v('kba'), text: v('kba-text'), gk: '#F06EB4' },
        ngr: { DEFAULT: v('ngr'), text: v('ngr-text'), gk: '#202020' },
        card: { yellow: '#FFD21F', red: '#E5383B' },
        ink: '#0C0E0D',
        chalk: '#F4F2EE',
      },
      fontFamily: {
        display: ['"Barlow Condensed"', 'sans-serif'],
        serif: ['"Instrument Serif"', 'serif'],
        sans: ['Geist', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      fontSize: {
        display: ['160px', '0.85'],
        score: '46px',
        'tv-bar': '42px',
        stat: '28px',
        'card-type': '22px',
        'insight-hero': ['38px', '1.2'],
        insight: ['25px', '1.2'],
        body: '16px',
        evidence: '14px',
        label: '11px',
      },
      borderRadius: { sm: '6px', md: '10px', lg: '16px', full: '9999px' },
      transitionTimingFunction: { out: 'cubic-bezier(0.22, 1, 0.36, 1)' },
    },
  },
  plugins: [],
};

export default config;
