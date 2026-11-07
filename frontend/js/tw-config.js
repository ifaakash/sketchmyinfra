/**
 * Shared Tailwind (CDN) config for workspace-themed pages. Load right after
 * cdn.tailwindcss.com.
 *
 * Tokens live in css/workspace.css as CSS variables; this maps them to
 * utilities (bg-smi-surface, text-smi-ink-3, ...) so dark mode is just the
 * variables flipping under .dark — no dark: variants needed.
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
          'on-accent': 'var(--smi-on-accent)',
          strong: 'var(--smi-strong)',
          'on-strong': 'var(--smi-on-strong)',
          ok: 'var(--smi-ok)',
          warn: 'var(--smi-warn)',
          'warn-bg': 'var(--smi-warn-bg)',
        },
        // Still used by markup that auth.js / ui.js / gallery.js / feedback.js inject
        brand: { 400: '#818cf8', 500: '#6366f1', 600: '#4f46e5' },
      },
      fontFamily: {
        sans: ['var(--smi-font-sans)'],
        mono: ['var(--smi-font-mono)'],
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
