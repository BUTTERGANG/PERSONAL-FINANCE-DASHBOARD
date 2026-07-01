# Architecture — Personal Finance Dashboard

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        REPLIT HOST                          │
│                                                             │
│  ┌──────────────────┐         ┌────────────────────────┐   │
│  │  Streamlit UI    │ ──HTTP──▶  FastAPI Backend        │   │
│  │  port 8501       │         │  port 8000              │   │
│  │  (public :80)    │◀──JSON──│                         │   │
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
User clicks "Link Account" in Streamlit
  → Streamlit opens /api/plaid/link page (served by FastAPI)
  → FastAPI calls Plaid API to get a link_token
  → Browser loads Plaid Link JS, initializes with link_token
  → User selects bank, completes OAuth / 2FA in Plaid's hosted UI
  → Plaid calls onSuccess(public_token)
  → Browser POSTs public_token to FastAPI /api/plaid/exchange
  → FastAPI exchanges public_token for access_token (one-time)
  → access_token is encrypted with Fernet and stored in SQLite
  → FastAPI immediately fetches balances + recent transactions
  → Success page shown; user returns to Streamlit dashboard
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
```

### Dashboard Data Load

```
Streamlit page loads
  → GET /api/accounts/ → list of accounts with balances
  → GET /api/transactions/?days=30 → recent transactions
  → GET /api/transactions/summary → spending by category
  → Render Plotly charts from response data
  (All API calls cached 5 minutes via @st.cache_data)
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

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Health check |
| GET | /api/accounts/ | List all linked accounts with balances |
| GET | /api/transactions/ | List transactions (filters: days, account_id) |
| GET | /api/transactions/summary | Spending by category |
| GET | /api/plaid/link | HTML page with Plaid Link JS |
| POST | /api/plaid/exchange | Exchange public_token → store access_token |
| POST | /api/sync/trigger | Manually trigger a full sync |
| GET | /api/sync/logs | Last 20 sync log entries |

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
| Frontend | Streamlit | Fastest path to interactive dashboard |
| Charts | Plotly | Interactive, dark-theme native |
| Database | SQLite | Zero-ops, single user, persisted on Replit disk |
