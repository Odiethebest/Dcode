import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      // Semantic color names → the CSS vars in index.css (single source of truth).
      colors: {
        paper: 'var(--paper)',
        surface: 'var(--surface)',
        sunk: 'var(--sunk)',
        'sunk-2': 'var(--sunk-2)',
        ink: 'var(--ink)',
        'ink-2': 'var(--ink-2)',
        'ink-3': 'var(--ink-3)',
        line: 'var(--line)',
        'line-2': 'var(--line-2)',
        brand: 'var(--brand)',
        'brand-hover': 'var(--brand-hover)',
        'brand-wash': 'var(--brand-wash)',
        good: 'var(--good)',
        'good-wash': 'var(--good-wash)',
        bad: 'var(--bad)',
        'bad-wash': 'var(--bad-wash)',
        warn: 'var(--warn)',
        'warn-wash': 'var(--warn-wash)',
      },
      // Override default `sans`/`mono` so unstyled text never drifts to system
      // fonts. `display` is the Newsreader "human understanding" voice.
      fontFamily: {
        display: ['"Newsreader Variable"', 'Georgia', '"Times New Roman"', 'serif'],
        sans: [
          '"IBM Plex Sans"',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          '"Segoe UI"',
          'Roboto',
          'sans-serif',
        ],
        mono: [
          '"IBM Plex Mono"',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Consolas',
          'monospace',
        ],
      },
      borderRadius: { card: '14px' },
      maxWidth: { content: '1180px' },
    },
  },
  plugins: [],
} satisfies Config;
