# Architecture — Personal Finance Dashboard

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        REPLIT HOST                          │
│                                                             │
│  ┌──────────────────┐         ┌────────────────────────┐   │
│  │  React Frontend  │ ──HTTP──▶  FastAPI Backend        │   │
│  │  (Vite dev: 5173)│         │  port 8000              │   │
│  │  (prod: static)  │◀──JSON──│                         │   │
│  └──────────────────┘         │  ┌──────────────────┐  │   │
│                               │  │  APScheduler     │  │   │
│                               │  │  (every 4h sync) │  │   │
│                               │  └──────────────────┘  │   │
│                               │                         │   │
│                               │  ┌──────────────────┐  │   │
│                               │  │  SQLite           │  │   │
│                               │  │  finance.db       │  │   │
│                               │  │  (on Replit disk) │  │   │
│                               │  └──────────────────┘  │   │
│                               └────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │                              │
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌──────────────────────────────┐
│   Plaid API     │          │   Fidelity OFX Endpoint      │
│                 │          │   ofx.fidelity.com           │
│  ┌───────────┐  │          │   (Direct Connect / Quicken  │
│  │  Chase    │  │          │    protocol — no 2FA)        │
│  │  Citi     │  │          └──────────────────────────────┘
│  │  PayPal   │  │
│  │  Venmo    │  │
│  └───────────┘  │
└─────────────────┘
```

---

## Data Flow

### First-Time Account Linking (Plaid)

```
User clicks "Link Account" in React UI
  → React navigates to /api/plaid/link (served by FastAPI)
  → FastAPI calls Plaid API to get a link_token
  → Browser loads Plaid Link JS, initializes with link_token
  → User selects bank, completes OAuth / 2FA in Plaid's hosted UI
  → Plaid calls onSuccess(public_token)
  → Browser POSTs public_token to FastAPI /api/plaid/exchange
  → FastAPI exchanges public_token for access_token (one-time)
  → access_token is encrypted with Fernet and stored in SQLite
  → FastAPI immediately fetches balances + recent transactions
  → Success page shown; user returns to React dashboard
```

### Recurring Sync (every 4 hours)

```
APScheduler fires
  → Queries SQLite for all active Plaid accounts
  → For each account:
      decrypt(plaid_access_token_enc) → access_token
      Plaid /transactions/sync → new transactions + balance updates
      Upsert into SQLite transactions table
      Update account.last_synced
  → OFX call to Fidelity:
      POST with credentials → OFX XML response
      Parse investment transactions
      Upsert into SQLite
  → Write SyncLog entry (success or error with message)
  → Capture net worth snapshot for the trend chart (one per UTC day)
```

### Dashboard Data Load

```
React page loads
  → GET /api/accounts/ → list of accounts with balances
  → GET /api/transactions/?days=30 → recent transactions
  → GET /api/transactions/summary → spending by category
  → GET /api/transactions/mom → month-over-month comparison
  → GET /api/networth/snapshots?days=180 → net worth trend
  → GET /api/budgets/alerts → budget warnings
  → Render Recharts charts from response data
  (All API calls cached 5 minutes via useAsync hook)
```

---

## Database Schema

### accounts
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | Plaid account_id or "fidelity_{acct_num}" |
| name | TEXT | Display name from institution |
| institution | TEXT | chase, citi, fidelity, paypal, venmo |
| account_type | TEXT | checking, savings, credit, investment |
| balance | REAL | Current balance |
| available_balance | REAL | Available (null for investment) |
| currency | TEXT | USD |
| plaid_access_token_enc | TEXT | Fernet-encrypted access token |
| plaid_item_id | TEXT | Plaid item identifier |
| is_active | BOOL | Soft delete flag |
| last_synced | DATETIME | UTC |
| created_at | DATETIME | UTC |

### transactions
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | Plaid transaction_id or "fidelity_{fitid}" |
| account_id | TEXT | FK → accounts.id |
| date | DATETIME | Transaction date |
| amount | REAL | Positive = debit, negative = credit/refund |
| description | TEXT | Merchant name or memo |
| category | TEXT | Plaid personal_finance_category |
| merchant | TEXT | Normalized merchant name |
| pending | BOOL | True if not yet settled |
| source | TEXT | "plaid" or "ofx" |
| created_at | DATETIME | When we recorded it |

### sync_logs
| Column | Type | Notes |
|--------|------|-------|
| id | INT PK | Auto-increment |
| account_id | TEXT | Nullable (null = full sync) |
| institution | TEXT | Which institution was synced |
| status | TEXT | "success" or "error" |
| transactions_added | INT | Count of new transactions |
| error_message | TEXT | Null on success |
| synced_at | DATETIME | UTC |

### budgets
| Column | Type | Notes |
|--------|------|-------|
| id | INT PK | Auto-increment |
| category | TEXT | Unique, e.g., "Food & Dining" |
| limit_amount | REAL | Monthly limit |
| created_at | DATETIME | UTC |
| updated_at | DATETIME | UTC, auto-updated |

### net_worth_snapshots
| Column | Type | Notes |
|--------|------|-------|
| id | INT PK | Auto-increment |
| day | TEXT | YYYY-MM-DD (UTC), unique dedupe key |
| captured_at | DATETIME | UTC |
| net_worth | REAL | Total assets - total debts |
| total_assets | REAL | Sum of non-credit account balances |
| total_debt | REAL | Sum of credit account balances |
| breakdown_json | TEXT | Per-institution balances at capture time |

### ignored_subscriptions
| Column | Type | Notes |
|--------|------|-------|
| id | INT PK | Auto-increment |
| merchant_key | TEXT | Unique, normalized merchant identifier |
| created_at | DATETIME | UTC |

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Health check |
| GET | /api/accounts/ | List all linked accounts with balances |
| DELETE | /api/accounts/{account_id} | Soft-delete (deactivate) an account |
| GET | /api/transactions/ | List transactions (filters: days, account_id, search, category) |
| GET | /api/transactions/summary | Spending by category |
| GET | /api/transactions/mom | Month-over-month comparison by category |
| GET | /api/transactions/categories | Distinct category list |
| GET | /api/plaid/link | HTML page with Plaid Link JS |
| POST | /api/plaid/exchange | Exchange public_token → store access_token |
| POST | /api/sync/trigger | Manually trigger a full sync |
| GET | /api/sync/logs | Last 20 sync log entries |
| GET | /api/networth/snapshots | Net worth history for trend chart |
| GET | /api/budgets/ | List all budgets with current spend & alert status |
| GET | /api/budgets/alerts | Categories at warning (80%) or danger (100%+) |
| POST | /api/budgets/ | Create or update a budget |
| DELETE | /api/budgets/{category} | Delete a budget |
| GET | /api/subscriptions/ | Detected recurring transactions |
| POST | /api/subscriptions/ignore | Dismiss a detected subscription |
| DELETE | /api/subscriptions/ignore/{merchant_key} | Restore a dismissed subscription |
| POST | /api/manual/accounts | Create a manual account (no Plaid) |
| PATCH | /api/manual/accounts/{account_id} | Update manual account balance |
| POST | /api/manual/import | Import CSV transactions to manual account |

---

## Security Architecture

See SECURITY.md for full threat model. Summary:

- **Plaid access tokens**: Encrypted (Fernet AES-128) before SQLite write
- **Encryption key**: Lives only in Replit Secrets (env var), never in code or DB
- **OFX credentials**: Live in Replit Secrets, never written to disk
- **Transport**: Replit provides HTTPS for all external traffic
- **Plaid is read-only**: Access tokens cannot initiate transfers
- **No passwords stored**: Plaid tokens replace passwords; OFX uses env vars

---

## Technology Choices

| Concern | Choice | Reason |
|---------|--------|--------|
| API framework | FastAPI | Async, auto-docs, type safety |
| ORM | SQLAlchemy 2.0 | Industry standard, good migrations path |
| Bank connectivity | Plaid | Handles OAuth/2FA, industry standard |
| Investment data | OFX direct | No 2FA friction, Fidelity supports it |
| Encryption | cryptography (Fernet) | Simple, strong, Python-native |
| Scheduling | APScheduler | Lightweight, in-process, no Redis needed |
| Frontend | React + Vite + Recharts | Modern, fast, type-safe, great charting |
| Charts | Recharts | Composable, responsive, dark-theme native |
| Database | SQLite | Zero-ops, single user, persisted on Replit disk |
| Styling | CSS Variables (custom design system) | Token-driven, light/dark native, no runtime deps |

---

## Frontend Architecture (React)

### State Management
- **Server state**: `useAsync` hook — consistent loading/error/data/reload pattern for all fetches
- **No global client state needed** — all data comes from API, UI is read-heavy
- **Theme**: CSS variables on `:root` / `[data-theme="dark"]`, toggled by setting `data-theme` on `<html>`

### Routing
- `react-router-dom` v6 with nested routes under `<App />` shell
- Sidebar navigation stays mounted; only page content swaps via `<Outlet />`

### Components
- **Design system**: All styling via CSS variables (theme.css) + component.css
- **Charts**: Recharts components in `components/charts/` reading colors from CSS vars at runtime
- **Tables**: DataTable with sticky headers, tabular numerals, hover highlight
- **Cards**: Consistent header/body layout, optional action slot

### Key Files
| File | Purpose |
|------|---------|
| `src/theme/theme.css` | All design tokens (colors, spacing, radius, shadows, fonts) |
| `src/theme/colors.ts` | Runtime accessor `chartColors()` for Recharts |
| `src/components/components.css` | Shared styles: Card, StatCard, Money, Badge, Button, Input, Table, EmptyState, Spinner, ProgressBar, PageHeader, Grid/Stack utilities |
| `src/hooks/useAsync.ts` | Universal async state hook |
| `src/services/api.ts` | Typed API client (mirrors FastAPI routes) |
| `src/services/types.ts` | TypeScript interfaces matching Pydantic schemas |
| `src/App.tsx` | Shell: sidebar, header, sync button, theme toggle, toast |
| `src/pages/Overview.tsx` | Complete MVP dashboard page |

---

## Sync Details

### Plaid Cursor-Based Sync
- Uses `/transactions/sync` — incremental, cursor-based
- Returns: `added`, `modified`, `removed`, `next_cursor`, `has_more`, `accounts` (with cached balances)
- **Free**: accounts with balances are included in the sync response — no separate `/accounts/get` call needed
- **Real-time balance**: `/accounts/balance/get` costs $0.10/call — only used on manual "Sync Now" button

### Net Worth Snapshots
- Captured at end of every `sync_all()` run
- Upserted by UTC calendar day (`day` = YYYY-MM-DD) — one row per day
- Includes breakdown JSON for future per-institution trend lines
- Assets = sum of non-credit accounts; Debts = sum of credit accounts; Net Worth = Assets - Debts

### Month-over-Month Comparison
- Compares this calendar month vs. last calendar month
- Last month prorated to same day-of-month for fair pace comparison
- Returns pct_change per category + totals

### Budget Alerts
- Warning at 80% of monthly limit, Danger at 100%+
- Computed per-category for current calendar month