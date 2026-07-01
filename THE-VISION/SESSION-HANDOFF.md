# Session Handoff — Personal Finance Dashboard

> Read this first at the start of every new Claude session.
> It gives you full context without needing to re-read code.

---

## What We're Building

A self-hosted personal finance dashboard running on Replit that pulls live data from five accounts — Fidelity (investment), Chase (checking), Citi (credit card), PayPal, and Venmo — normalizes everything into a single SQLite database, and presents a unified dashboard showing net worth, spending by category, transaction history, and balance trends.

**Design principle:** Zero daily friction. Authenticate once per institution; background sync handles everything after that.

---

## Architecture in One Paragraph

**FastAPI** backend (port 8000) handles all data fetching and storage. It uses **Plaid** to connect Chase, Citi, PayPal, and Venmo (OAuth-based, no stored passwords, handles 2FA automatically). It uses **OFX direct connect** to pull Fidelity data (same protocol Quicken uses — no 2FA required per-pull). All data lands in **SQLite** (`finance.db`). Plaid access tokens are encrypted at rest using Fernet symmetric encryption before being stored. An **APScheduler** job syncs every 4 hours automatically. The **Streamlit** frontend (port 8501) calls the FastAPI REST endpoints and renders interactive Plotly charts.

---

## File Map — Where Things Live

```
backend/
  config.py          ← All env var settings (pydantic-settings)
  models.py          ← SQLAlchemy: Account, Transaction, SyncLog
  database.py        ← Engine setup, get_db() dependency
  crypto.py          ← Fernet encrypt/decrypt for token storage
  plaid_client.py    ← Link token creation, token exchange, balance/txn fetch
  fidelity_client.py ← OFX direct connect to Fidelity
  sync.py            ← Orchestrates all account syncs
  main.py            ← FastAPI app, CORS, scheduler startup
  api/
    accounts.py      ← GET /api/accounts/
    transactions.py  ← GET /api/transactions/, /summary
    plaid_routes.py  ← GET /api/plaid/link, POST /api/plaid/exchange
    sync_routes.py   ← POST /api/sync/trigger, GET /api/sync/logs

frontend/
  app.py             ← Streamlit entry point, page config, CSS
  utils/api.py       ← HTTP client wrapper for all backend calls
  pages/
    1_Overview.py    ← Net worth, account cards, spending charts
    2_Transactions.py← Filterable transaction table + charts
    3_Accounts.py    ← Account management, sync status
    4_Link_Account.py← Plaid Link flow, Fidelity OFX setup
    5_Settings.py    ← Sync config, export data

THE-VISION/
  ARCHITECTURE.md    ← Detailed system diagram and data flow
  SETUP.md           ← Step-by-step setup from zero
  SECURITY.md        ← Threat model, what's encrypted, what's safe
  SESSION-HANDOFF.md ← THIS FILE
  ROADMAP.md         ← MVP done, Phase 2/3 backlog
  GITHUB-SETUP.md    ← Private repo setup, access control

scripts/
  generate_key.py    ← One-time Fernet key generation
```

---

## Current Status

| Layer | Status | Notes |
|-------|--------|-------|
| Backend API | ✅ Built | FastAPI, all routes implemented |
| Database models | ✅ Built | Account, Transaction, SyncLog |
| Plaid integration | ✅ Built | Link + exchange + sync |
| Fidelity OFX | ✅ Built | Needs credential testing with real account |
| Encryption | ✅ Built | Fernet, key from env var |
| Auto-sync scheduler | ✅ Built | APScheduler, configurable interval |
| Streamlit frontend | ✅ Built | 5 pages with Plotly charts |
| Deployed to Replit | ⬜ Pending | See SETUP.md for deployment steps |
| Real accounts linked | ⬜ Pending | Needs Plaid dev account + Fidelity OFX credentials |

---

## Key Decisions Made (and Why)

**Plaid for Chase/Citi/PayPal/Venmo, not scraping**
Scrapers break every few weeks when banks update their UIs. Plaid handles OAuth and 2FA natively. Free dev tier covers personal use indefinitely.

**OFX for Fidelity, not Plaid**
Fidelity's Plaid connection is unreliable (it often prompts 2FA). OFX direct connect is the protocol Quicken uses — it works silently with username/password, no browser involved.

**Replit with Always On (not local)**
User prioritized accessibility from any device. Always On (~$7/mo or included in credits) keeps the scheduler running continuously.

**SQLite (not Postgres)**
Single-user personal app — SQLite is simpler, zero maintenance, and runs on Replit's persistent disk. Can migrate to Postgres later if needed.

**Streamlit (not React)**
Fastest path to a working, interactive dashboard. All Python — no context switching. Can port to React in Phase 2 if more custom UI is needed.

**Encrypted tokens at rest**
Plaid access tokens stored in SQLite are encrypted with Fernet before write. Encryption key lives in Replit Secrets. This means the database file alone is worthless without the key.

---

## What To Do Next

1. Create Plaid developer account at dashboard.plaid.com
2. Generate encryption key: `python scripts/generate_key.py`
3. Add all secrets to Replit Secrets panel (see SETUP.md)
4. Deploy to Replit and run `bash run.sh`
5. Link accounts via the "Link Account" page in the dashboard
6. Test Fidelity OFX connection — may need PIN separate from web password (see SETUP.md)

---

## Gotchas / Non-Obvious Things

- **Plaid sandbox vs development**: Sandbox uses fake data. Switch `PLAID_ENV=development` to connect real accounts. Development mode has a 100-item limit (more than enough for personal use).
- **Fidelity OFX PIN**: Some Fidelity users have a separate OFX/Quicken PIN. If your regular password doesn't work, call Fidelity and ask to enable "Quicken Direct Connect" — they'll give you a PIN.
- **Plaid credit card balances**: Plaid returns the current balance owed on credit cards as a positive number. The Overview page subtracts credit balances from net worth automatically (see `calculate_net_worth()` in Overview.py).
- **Streamlit reruns**: Streamlit reruns the entire script on every interaction. API calls are cached with `@st.cache_data(ttl=300)` to prevent hammering the backend.
- **Database file**: `finance.db` contains your actual transaction data. It's git-ignored. Back it up manually or let Replit handle persistence.
- **Port mapping on Replit**: FastAPI is on port 8000, Streamlit on 8501. The `.replit` file maps 8501 to port 80 (the public-facing URL). Both are accessible externally.
