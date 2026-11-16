/**
 * Shared Tailwind (CDN) config for every public page. Load right after
 * cdn.tailwindcss.com.
 *
 * Tokens live in css/workspace.css as CSS variables; `smi-*` maps them to
 * utilities (bg-smi-surface, text-smi-ink-3, ...) so dark mode is just the
 * variables flipping under .dark — no dark: variants needed.
 *
 * Brand: navy #14213D, cream #F4EDE0, coral #FF6B5B.
 * `gray` and `brand` are remapped so pages written with stock classes
 * (text-gray-500, dark:bg-gray-950, bg-brand-600, ...) pick up the brand
 * without rewriting their markup: light steps are cream, dark steps navy,
 * brand is coral. Contrast checked for the pairs those pages use:
 *   gray-500 on white 5.6 · gray-400 on gray-950 7.3 · brand-400 on gray-900 7.0
 *   white on brand-600 5.2 (never white on brand-500: 2.8)
 */
tailwind.config = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        smi: {
          bg: 'var(--smi-bg)',
          surface: 'var(--smi-surface)',
          'surface-2': 'var(--smi-surface-2)',
          canvas: 'var(--smi-canvas)',
          selected: 'var(--smi-selected)',
          border: 'var(--smi-border)',
          'border-strong': 'var(--smi-border-strong)',
          'border-soft': 'var(--smi-border-soft)',
          ink: 'var(--smi-ink)',
          'ink-2': 'var(--smi-ink-2)',
          'ink-3': 'var(--smi-ink-3)',
          'ink-faint': 'var(--smi-ink-faint)',
          accent: 'var(--smi-accent)',
          'accent-hover': 'var(--smi-accent-hover)',
          'accent-text': 'var(--smi-accent-text)',
          'accent-soft': 'var(--smi-accent-soft)',
          'on-accent': 'var(--smi-on-accent)',
          strong: 'var(--smi-strong)',
          'strong-hover': 'var(--smi-strong-hover)',
          'on-strong': 'var(--smi-on-strong)',
          ok: 'var(--smi-ok)',
          warn: 'var(--smi-warn)',
          'warn-bg': 'var(--smi-warn-bg)',
        },
        navy: '#14213D',
        cream: '#F4EDE0',
        coral: '#FF6B5B',
        gray: {
          50: '#FBF7F0',
          100: '#F4EDE0',   // cream
          200: '#E6DCCB',
          300: '#CBC3B4',
          400: '#A8A396',
          500: '#5E6880',
          600: '#4A5570',
          700: '#3B4864',
          800: '#1B2B4B',
          900: '#14213D',   // navy
          950: '#0B1426',
        },
        brand: {
          50: '#FFF1EE',
          100: '#FFE3DE',
          300: '#FFB3A9',
          400: '#FF8A7D',   // coral text on navy
          500: '#FF6B5B',   // coral fill (navy text only)
          600: '#C8372D',   // deep coral: white text 5.2
          700: '#A02A22',
          800: '#5C1E1A',
          900: '#2E1412',
        },
      },
      fontFamily: {
        sans: ['var(--smi-font-sans, Inter)', 'system-ui', 'sans-serif'],
        mono: ['var(--smi-font-mono, "JetBrains Mono")', 'ui-monospace', 'monospace'],
      },
      height: {
        header: 'var(--smi-header-h)',
        status: 'var(--smi-statusbar-h)',
      },
      boxShadow: {
        'smi-sm': 'var(--smi-shadow-sm)',
        smi: 'var(--smi-shadow)',
      },
    }
  }
};
