// Runtime access to the CSS design tokens, for libraries (Recharts) that need
// concrete color strings rather than CSS var() references. Reading the computed
// value means charts automatically follow light/dark theme switches.

export function cssVar(name: string): string {
  if (typeof window === 'undefined') return '';
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// Categorical series order — fixed, never cycled (dataviz rule). Validated
// palette: indigo, green, red, amber, sky. Used only where a chart genuinely
// has multiple series; single-series charts use the accent.
export const SERIES = ['#6366f1', '#16a34a', '#dc2626', '#d97706', '#0ea5e9'] as const;

export const chartColors = () => ({
  accent: cssVar('--accent') || '#6366f1',
  positive: cssVar('--positive') || '#16a34a',
  negative: cssVar('--negative') || '#dc2626',
  warning: cssVar('--warning') || '#d97706',
  grid: cssVar('--chart-grid') || '#eceef1',
  surface: cssVar('--chart-surface') || '#ffffff',
  text: cssVar('--text') || '#1a1d23',
  textMuted: cssVar('--text-muted') || '#6b7280',
  border: cssVar('--border') || '#e5e7eb',
});
