# Roadmap — Personal Finance Dashboard

## Current Focus (2026-07) — Document Upload

**Plaid developer access is still pending approval**, so live bank sync is built but
dormant. Until that clears, the product's primary data path is **document upload**:
manual accounts + CSV import + PDF statement import. All of it is built and working —
this section tracks the polish that makes it the reliable, standalone way to use the app.

- [x] Manual accounts (checking/savings/credit/investment/loan/asset/cash)
- [x] CSV import — sequential multi-file wizard, column auto-mapping, sign flip, idempotent re-import
- [x] **PDF statement import — section-aware, self-reconciling parser.** Six statement
      types tuned against real samples, each verified to the penny against the
      statement's own printed totals: **Chase checking**, **Citi credit** (Costco Visa),
      **PayPal credit**, **Venmo credit**, **Fidelity brokerage** (investment), and
      **Fidelity crypto**. 45 parser tests. See `backend/pdf_parser.py` and
      `tests/test_pdf_parser.py`.
- [x] **Reconciliation self-check** — parsed section sums are compared to the
      statement's printed totals (and the credit-card / checking balance identity);
      the Import preview shows "reconciled to the penny", "review needed", or "no
      check available" before you import.
- [x] **Statement balances + holdings surfaced** — the preview shows every headline
      figure (new/ending balance, min payment, due date, credit limit) and, for
      Fidelity, the holdings table (symbol, quantity, price, market value, cost
      basis, unrealized gain).
- [x] **Balance sync on import** — importing a statement can set the account's
      balance to the statement's ending/account value (opt-in checkbox). Holdings-only
      statements (Fidelity) import via balance sync with no transactions.
- [x] **Transaction categorization** — a shared merchant extractor peels bank noise
      (transaction-type prefixes, reference ids, `Sq */Klarna*/Wl *` aggregator
      wrappers, location tails) down to a clean brand; a rule-based auto-categorizer
      buckets rows using system rules (Income / Transfer / Payment / Fees & Interest /
      Cash & ATM — so non-spend never counts as spend), a built-in merchant seed map,
      and learned merchant→category rules. Imports auto-categorize; the Transactions
      page has an inline category dropdown + an "Auto-categorize N" action. Correcting
      a merchant learns a rule that re-applies to past rows and future imports.
      `backend/categorize.py`, 30 tests. (Also fixed a latent bug: the old
      `_merchant_key` collapsed every card purchase to "card purchase", breaking
      subscription grouping — now shared with the new extractor.)
- [ ] **Persist holdings** — holdings are parsed + displayed but not stored; a
      `Holding` table would enable a portfolio view (positions, cost basis, gain/loss)
- [ ] **More statement types** — Discover, Amex, and other banks as samples arrive
      (each new type is a declarative config + a test fixture)
- [ ] **Import history / undo** — show what each import added; allow removing a bad import batch
- [ ] **OFX file upload** — accept `.ofx`/`.qfx` downloads (many banks export these; more structured than PDF) as a third import format

> When Plaid access is finally granted, live sync layers *on top of* this — document
> upload stays useful for backfilling history Plaid won't provide.

---

## MVP (Built ✅)

The foundation is complete. These features are live:

- [x] Plaid integration for Chase, Citi, PayPal, Venmo
- [x] Fidelity OFX direct connect (no 2FA)
- [x] Encrypted Plaid token storage at rest
- [x] SQLite database (accounts, transactions, sync logs)
- [x] Background auto-sync every 4 hours
- [x] Manual sync trigger
- [x] FastAPI REST backend with all endpoints
- [x] React + Recharts frontend — all 8 pages built
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
  - Clean modern fintech aesthetic (light + dark, indigo accent, calm neutrals, rounded cards, Inter font, tabular-nums)
  - *(An earlier "Bloomberg Terminal" neon theme was tried and replaced 2026-07-02.)*
  - Better mobile responsiveness with stacked grids
- [x] Dark/light theme toggle (working, persists to localStorage)
- [x] Budget alerts with color-coded thresholds
- [x] Enhanced month-over-month comparison table

### Data Intelligence
- [x] **Budget tracking**: set monthly budget per category, show progress bars
- [ ] **Spending alerts**: notify (email or push) when category exceeds budget — *in-app banner exists; external notification not built*
- [x] **Recurring transaction detection**: automatically identify subscriptions
- [x] **Month-over-month comparison**: "You spent 18% more on Food this month"
- [x] **Net worth trend**: line chart of total net worth over time (snapshots implemented in MVP)

### Security Upgrades
- [x] **App-level PIN gate**: `PinAuthMiddleware` guards all `/api/*` (constant-time
      compare; gate off when `dashboard_pin` is unset). React `AuthGate` + `pin.ts`
      prompt for and store the PIN.
- [ ] **SQLCipher**: encrypt the entire SQLite file, not just tokens
- [ ] **Audit log**: record every time the dashboard is accessed

### Data
- [x] **Historical import**: CSV upload from bank statements to backfill history
- [x] **PDF statement import**: section-aware, self-reconciling parser — 6 statement
      types tuned to real samples (Chase checking, Citi/PayPal/Venmo credit, Fidelity
      brokerage + crypto), each verified to the penny against printed totals
- [x] **Investment holdings parsing**: Fidelity brokerage + crypto statements parse
      positions (symbol, quantity, price, market value, cost basis, unrealized gain)
      and reconcile against the account value — *displayed in the import preview; not
      yet persisted to a holdings table*
- [x] **Transaction categorization override**: inline per-row category dropdown on
      the Transactions page; correcting a merchant learns a rule and re-applies it
- [x] **Merchant normalization**: `extract_merchant()` unwraps `Sq */Klarna*/Wl *`
      aggregators and strips prefixes/ids/location tails to a clean brand
      (`P928300… Standard UBER` → `UBER`, `Klarna*Ebay` → `Ebay`)

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
| **Plaid dev access not yet granted** | **Blocked** | Waiting on Plaid approval; document upload is the working data path meanwhile |
| PDF parser only covers 6 statement types | Known | Each new bank is a declarative config + a test fixture; add Discover/Amex/etc. as samples arrive |
| Investment holdings parsed but not persisted | Known | Add a `Holding` table + portfolio view; today they're shown in the import preview only |
| Merchant extraction is heuristic (regex) | Known | Good on the 6 known statement formats; a new bank's noise may need a new peel rule. Learned rules + the seed map cover the gaps |
| Transaction data not encrypted at rest | Deferred | SQLCipher |
| Venmo transaction detail from Plaid is limited | Known | Phase 3: direct scraping (only relevant once Plaid works) |
| Fidelity investment positions not pulled (only transactions) | Deferred | Add InvStmtRq for positions |

---

## React Frontend Page Status

All eight pages are built and styled (dedicated stylesheets, light/dark theme).

| Page | Status | Notes |
|------|--------|-------|
| Overview | ✅ Built | Net worth, assets/debt, 30-day spend, net worth trend, MoM movers, accounts, budget-alert banner |
| Transactions | ✅ Built | Filterable table (date/account/category/search) |
| Accounts | ✅ Built | Balance cards, sync status, manual account create/edit |
| Budgets | ✅ Built | Budget list, progress bars, create/edit |
| Subscriptions | ✅ Built | Detected recurring list, dismiss/restore |
| Import | ✅ Built | CSV multi-file wizard + PDF statement upload (preview → confirm) |
| Link Account | ✅ Built | Opens server-rendered Plaid Link page; Fidelity OFX setup instructions (dormant until Plaid access) |
| Settings | ✅ Built | Sync trigger, sync logs, CSV export |

> `pages/Placeholder.tsx` still exists but is no longer routed to.

---

## Development Principles

1. **Backend-first**: API contracts locked before UI work
2. **Type-safe end-to-end**: Pydantic ↔ TypeScript interfaces shared via `types.ts`
3. **Design system consistency**: Every new component uses CSS variables from `theme.css`
4. **No global state library**: `useAsync` hook handles server state; theme is CSS-based
5. **Chart colors from theme**: Recharts reads `chartColors()` at render time for live light/dark switching