# Roadmap — Personal Finance Dashboard

## MVP (Built ✅)

The foundation is complete. These features are live:

- [x] Plaid integration for Chase, Citi, PayPal, Venmo
- [x] Fidelity OFX direct connect (no 2FA)
- [x] Encrypted Plaid token storage at rest
- [x] SQLite database (accounts, transactions, sync logs)
- [x] Background auto-sync every 4 hours
- [x] Manual sync trigger
- [x] FastAPI REST backend with all endpoints
- [x] React + Recharts frontend — Overview page complete
- [x] Net worth overview with account balance cards
- [x] Spending by category (pie chart — Recharts)
- [x] Spending over time (bar chart — Recharts)
- [x] Transaction table with filters (date, account, category, search)
- [x] Account management page with sync status
- [x] Settings page with sync logs
- [x] Data export (CSV)
- [x] THE-VISION documentation suite
- [x] GitHub private repo setup guide
- [x] Replit deployment configuration

---

## Phase 2 — Polish & Intelligence

Nice-to-haves once the MVP is stable and accounts are flowing.

### UI Upgrade (React Frontend)
- [x] Port frontend from Streamlit to React + Recharts
  - Bloomberg Terminal aesthetic (dark mode, amber accents, monospace)
  - Dense, efficient data display optimized for desktop + mobile
  - Custom card layout with terminal-style selection highlights
  - Better mobile responsiveness with stacked grids
- [x] Dark/light theme toggle (infrastructure ready)
- [x] Budget alerts with color-coded thresholds
- [x] Enhanced month-over-month comparison table

### Data Intelligence
- [ ] **Budget tracking**: set monthly budget per category, show progress bars
- [ ] **Spending alerts**: notify (email or push) when category exceeds budget
- [ ] **Recurring transaction detection**: automatically identify subscriptions
- [ ] **Month-over-month comparison**: "You spent 18% more on Food this month"
- [ ] **Net worth trend**: line chart of total net worth over time (requires snapshots — ✅ implemented in MVP)

### Security Upgrades
- [ ] **SQLCipher**: encrypt the entire SQLite file, not just tokens
- [ ] **App-level password**: simple PIN or passphrase to open the dashboard
- [ ] **Audit log**: record every time the dashboard is accessed

### Data
- [ ] **Historical import**: allow CSV upload from bank statements to backfill history
- [ ] **Transaction categorization override**: let user re-categorize transactions
- [ ] **Merchant normalization**: "AMZN*12345" → "Amazon"

---

## Phase 3 — Advanced

For when this becomes a serious tool.

### New Data Sources
- [ ] **Venmo via direct scraping** (Plaid's Venmo connection has gaps)
- [ ] **Betterment / Wealthfront via OFX or scraping**
- [ ] **Real estate value** (Zillow API for home equity tracking)
- [ ] **Crypto holdings** (Coinbase API, CoinGecko for prices)
- [ ] **Manual accounts**: enter 401k, car value, mortgage balance

### Infrastructure
- [ ] **Migrate to Postgres** (when data volume grows)
- [ ] **Docker Compose setup** (for running locally without Replit)
- [ ] **Scheduled database backups** to S3 or Google Drive
- [ ] **GitHub Actions CI**: lint, type check, test on every push

### Analytics
- [ ] **Annual spending report** (PDF export)
- [ ] **Tax-year summaries by category**
- [ ] **Investment return tracking** (Fidelity positions vs cost basis)
- [ ] **Cash flow projection**: based on recurring transactions, project next 30 days

---

## Known Limitations / Deferred Decisions

| Issue | Status | Plan |
|-------|--------|------|
| Transaction data not encrypted | Deferred | Phase 2: SQLCipher |
| Venmo transaction detail from Plaid is limited | Known | Phase 3: direct scraping |
| Fidelity investment positions not pulled (only transactions) | Deferred | Phase 2: add InvStmtRq for positions |
| No auth on dashboard UI | Intentional for now | Phase 2: simple PIN gate |
| Plaid Sandbox → Development requires manual approval | Pending | User to request dev access |

---

## React Frontend Page Status

| Page | Status | Notes |
|------|--------|-------|
| Overview | ✅ Complete | Full dashboard with all charts, metrics, accounts list |
| Transactions | 🟡 Placeholder | Next: filterable table, category pie, spending timeline |
| Accounts | 🟡 Placeholder | Next: balance cards, sync status, manual account form |
| Budgets | 🟡 Placeholder | Next: budget list, progress bars, create/edit modal |
| Subscriptions | 🟡 Placeholder | Next: detected recurring list, dismiss action |
| Import | 🟡 Placeholder | Next: CSV upload, column mapping, preview |
| Link Account | 🟡 Placeholder | Next: Plaid Link embed, Fidelity credential form |
| Settings | 🟡 Placeholder | Next: sync interval, export, sync logs, theme toggle |

---

## Development Principles

1. **Backend-first**: API contracts locked before UI work
2. **Type-safe end-to-end**: Pydantic ↔ TypeScript interfaces shared via `types.ts`
3. **Design system consistency**: Every new component uses CSS variables from `theme.css`
4. **No global state library**: `useAsync` hook handles server state; theme is CSS-based
5. **Chart colors from theme**: Recharts reads `chartColors()` at render time for live light/dark switching