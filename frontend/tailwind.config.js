/** PitchVision design tokens. Three type sizes only: label 12, text 15, figure 32. */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    fontSize: {
      label: ['12px', { lineHeight: '16px' }],
      text: ['15px', { lineHeight: '22px' }],
      fig: ['32px', { lineHeight: '34px' }],
    },
    fontFamily: {
      sans: ['system-ui', '-apple-system', 'BlinkMacSystemFont', 'Barlow', 'sans-serif'],
      board: ['"Barlow Condensed"', 'Barlow', 'system-ui', 'sans-serif'],
    },
    borderRadius: { none: '0', plate: '2px', ctl: '8px', full: '9999px' },
    extend: {
      colors: {
        bg: 'var(--bg)', surface: 'var(--surface)', rule: 'var(--rule)', 'rule-strong': 'var(--rule-strong)',
        ink: 'var(--ink)', 'ink-2': 'var(--ink-2)', plate: 'var(--plate)', 'plate-ink': 'var(--plate-ink)',
        'plate-dim': 'var(--plate-dim)', accent: 'var(--accent)', 'accent-ink': 'var(--accent-ink)',
        green: 'var(--green)', red: 'var(--red)', turf: 'var(--turf)', strip: 'var(--strip)',
      },
    },
  },
  plugins: [],
}
