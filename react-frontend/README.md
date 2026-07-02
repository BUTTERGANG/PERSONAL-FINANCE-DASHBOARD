# Finance Dashboard - React Frontend

Clean fintech React frontend for the Personal Finance Dashboard.

## Features

- **Modern fintech aesthetic** - Light/dark mode with CSS variable design system
- **Monospace data display** - JetBrains Mono for numbers, Inter for UI
- **Dense, efficient layout** - Optimized for desktop, stacks on mobile
- **Terminal-style selection highlights** - Accent borders on active nav items
- **Theme-consistent charts** - Recharts reads CSS variables at runtime

## Development

```bash
cd react-frontend
npm install
npm run dev
```

The dev server runs on `http://localhost:5173` and proxies API requests to the FastAPI backend at `http://localhost:8000`.

## Build

```bash
npm run build
```

Outputs to `dist/` folder for production deployment.

## Design System (CSS Variables)

All colors, spacing, radii, and shadows defined in `src/theme/theme.css` as CSS custom properties on `:root` (light) and `[data-theme="dark"]` (dark).

### Color Palette

| Token | Light | Dark | Purpose |
|-------|-------|------|---------|
| `--bg` | #f7f8fa | #0f1115 | Page background |
| `--surface` | #ffffff | #181b22 | Card/surface background |
| `--surface-2` | #f2f4f7 | #1f232b | Subtle inset (headers, inputs) |
| `--sidebar` | #ffffff | #14171d | Sidebar background |
| `--text` | #1a1d23 | #e6e8ec | Primary text |
| `--text-secondary` | #4b5563 | #a8afba | Secondary text |
| `--text-muted` | #6b7280 | #7c8492 | Muted text |
| `--border` | #e5e7eb | #272b33 | Borders |
| `--accent` | #6366f1 | #818cf8 | Primary brand (indigo) |
| `--positive` | #16a34a | #4ade80 | Gains/income |
| `--negative` | #dc2626 | #f87171 | Losses/debt |
| `--warning` | #d97706 | #fbbf24 | Alerts/budgets |

### Chart Surface (for Recharts)

| Token | Light | Dark |
|-------|-------|------|
| `--chart-surface` | #ffffff | #181b22 |
| `--chart-grid` | #eceef1 | #262a32 |

### Typography

- `--font-sans`: Inter (UI, body)
- `--font-mono`: JetBrains Mono (numbers, tables, code)

### Spacing Scale

`--space-1` (4px) through `--space-6` (32px)

### Radius

`--radius-lg` (12px), `--radius` (10px), `--radius-sm` (8px), `--radius-pill` (999px)

## Pages

| Path | Status | Description |
|------|--------|-------------|
| `/overview` | ✅ Complete | Net worth, metrics, trend chart, MoM comparison, accounts |
| `/transactions` | 🟡 Placeholder | Filterable table, category pie, timeline (Phase 2) |
| `/accounts` | 🟡 Placeholder | Balance cards, sync status, manual accounts (Phase 2) |
| `/link` | 🟡 Placeholder | Plaid Link embed, Fidelity form (Phase 2) |
| `/budgets` | 🟡 Placeholder | Budget list, progress bars, create/edit (Phase 2) |
| `/subscriptions` | 🟡 Placeholder | Detected recurring, dismiss action (Phase 2) |
| `/import` | 🟡 Placeholder | CSV upload, column mapping, preview (Phase 2) |
| `/settings` | 🟡 Placeholder | Sync config, export, logs, theme (Phase 2) |

## Component Library

Shared components in `src/components/`:

| Component | Purpose |
|-----------|---------|
| `Card` | Consistent header/body layout with optional action slot |
| `StatCard` | Metric display with accent bar, value, optional delta |
| `Money` | Formatted currency with positive/negative coloring |
| `Badge` | Status tags (pos/neg/warn/accent variants) |
| `DataTable` | Sortable, sticky-header table with tabular numerals |
| `EmptyState` | Centered icon + title + hint for empty data |
| `Spinner` | Loading indicator |
| `ProgressBar` | Horizontal progress with color |
| `PageHeader` | Title + subtitle + actions row |
| `ThemeToggle` | Light/dark switch (persists to localStorage) |
| `charts/AreaTrend` | Net worth area chart with gradient fill |
| `charts/BarCategory` | Spending by category horizontal bars |
| `charts/ProgressBar` | Budget progress visualization |

## Hooks

- `useAsync` — Universal fetch state (data/loading/error/reload)

## Services

- `api.ts` — Typed client for all FastAPI endpoints
- `types.ts` — TypeScript interfaces mirroring Pydantic schemas