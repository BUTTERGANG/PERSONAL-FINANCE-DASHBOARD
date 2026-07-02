# Session Handoff — Personal Finance Dashboard

> Read this first at the start of every new Claude session.
> It gives you full context without needing to re-read code.

---

## What We're Building

A self-hosted personal finance dashboard running on Replit that pulls live data from five accounts — Fidelity (investment), Chase (checking), Citi (credit card), PayPal, and Venmo — normalizes everything into a single SQLite database, and presents a unified dashboard showing net worth, spending by category, transaction history, and balance trends.

**Design principle:** Zero daily friction. Authenticate once per institution; background sync handles everything after that.

---

## Architecture in One Paragraph

**FastAPI** backend (port 8000) handles all data fetching and storage. It uses **Plaid** to connect Chase, Citi, PayPal, and Venmo (OAuth-based, no stored passwords, handles 2FA automatically). It uses **OFX direct connect** to pull Fidelity data (same protocol Quicken uses — no 2FA required per-pull). All data lands in **SQLite** (`finance.db`). Plaid access tokens are encrypted at rest using Fernet symmetric encryption before being stored. An **APScheduler** job syncs every 4 hours automatically. The **React + Recharts** frontend (port 5173 via Vite dev, built to static assets for prod) calls the FastAPI REST endpoints and renders interactive charts.

---

## File Map — Where Things Live

```
backend/
  config.py           ← All env var settings (pydantic-settings)
  models.py           ← SQLAlchemy: Account, Transaction, SyncLog, Budget, NetWorthSnapshot, IgnoredSubscription
  database.py         ← Engine setup, get_db() dependency
  crypto.py           ← Fernet encrypt/decrypt for token storage
  plaid_client.py     ← Link token creation, token exchange, balance/txn fetch
  fidelity_client.py  ← OFX direct connect to Fidelity
  sync.py             ← Orchestrates all account syncs
  main.py             ← FastAPI app, CORS, scheduler startup
  api/
    accounts.py       ← GET /api/accounts/
    transactions.py   ← GET /api/transactions/, /summary, /mom, /categories
    plaid_routes.py   ← GET /api/plaid/link, POST /api/plaid/exchange
    sync_routes.py    ← POST /api/sync/trigger, GET /api/sync/logs
    networth.py       ← GET /api/networth/snapshots
    budgets.py        ← GET /api/budgets/, /alerts, POST/DELETE /budgets/
    subscriptions.py  ← GET /api/subscriptions/, POST/DELETE /ignore
    manual.py         ← POST /manual/accounts, PATCH /manual/accounts/:id, POST /manual/import

react-frontend/       ← NEW: React + Vite + Recharts frontend (Phase 2 UI upgrade)
  src/
    App.tsx           ← Shell: sidebar, header, sync button, theme toggle
    main.tsx          ← Entry point, router setup
    hooks/useAsync.ts ← Reusable fetch state hook (data/loading/error/reload)
    services/
      api.ts          ← All backend endpoints typed
      types.ts        ← TypeScript interfaces mirroring FastAPI Pydantic models
    components/
      Card.tsx, StatCard.tsx, Money.tsx, Badge.tsx, DataTable.tsx, ...
      charts/
        AreaTrend.tsx  ← Net worth trend chart (Recharts)
        BarCategory.tsx
        ProgressBar.tsx
    pages/
      Overview.tsx     ← Net worth, assets/debt, spending, net worth trend, MoM movers, accounts list
      Transactions.tsx ← Placeholder (next pass)
      Accounts.tsx     ← Placeholder
      Budgets.tsx      ← Placeholder
      Subscriptions.tsx← Placeholder
      Import.tsx       ← Placeholder
      LinkAccount.tsx  ← Placeholder
      Settings.tsx     ← Placeholder
      Placeholder.tsx  ← Shared "Coming in next pass" component
    theme/
      theme.css        ← CSS variables design system (light/dark, tokens)
      colors.ts        ← Runtime chart color accessor (reads CSS vars)
    components.css     ← Shared component styles (cards, tables, badges, buttons, inputs, spinner, empty state)

frontend/             ← OLD: Streamlit dashboard (5 pages) — kept for reference, not deployed
THE-VISION/
  ARCHITECTURE.md     ← Detailed system diagram and data flow
  SETUP.md            ← Step-by-step setup from zero
  SECURITY.md         ← Threat model, what's encrypted, what's safe to commit
  SESSION-HANDOFF.md  ← THIS FILE
  ROADMAP.md          ← MVP done, Phase 2/3 backlog
  GITHUB-SETUP.md     ← Private repo setup and access control

scripts/
  generate_key.py     ← One-time Fernet key generation
```

---

## Current Status

| Layer | Status | Notes |
|-------|--------|-------|
| Backend API | ✅ Built | FastAPI, all routes implemented |
| Database models | ✅ Built | Account, Transaction, SyncLog, Budget, NetWorthSnapshot, IgnoredSubscription |
| Plaid integration | ✅ Built | Link + exchange + sync (cursor-based, incremental) |
| Fidelity OFX | ✅ Built | Needs credential testing with real account |
| Encryption | ✅ Built | Fernet, key from env var |
| Auto-sync scheduler | ✅ Built | APScheduler, configurable interval |
| **React frontend** | **✅ Phase 1 complete** | Overview page fully built with charts, metrics, MoM comparison; 7 placeholder pages ready for Phase 2 |
| Deployed to Replit | ⬜ Pending | See SETUP.md for deployment steps |
| Real accounts linked | ⬜ Pending | Needs Plaid dev account + Fidelity OFX credentials |

---

## Key Decisions Made (and Why)

**Plaid for Chase/Citi/PayPal/Venmo, not scraping**
Scrapers break every few weeks when banks update their UIs. Plaid handles OAuth and 2FA natively. Free dev tier covers personal use indefinitely.

**OFX for Fidelity, not Plaid**
Fidelity's Plaid connection is unreliable (often prompts 2FA). OFX direct connect is the protocol Quicken uses — it works silently with username/password, no browser involved.

**Replit with Always On (not local)**
User prioritized accessibility from any device. Always On (~$7/mo or included in credits) keeps the scheduler running continuously.

**SQLite (not Postgres)**
Single-user personal app — SQLite is simpler, zero maintenance, and runs on Replit's persistent disk. Can migrate to Postgres later if needed.

**React + Recharts (not Streamlit)**
Phase 2 UI upgrade. Clean fintech aesthetic (dark mode, amber accents, monospace), dense data display optimized for desktop + mobile, custom card layout with terminal-style selection highlights.

**Encrypted tokens at rest**
Plaid access tokens stored in SQLite are encrypted with Fernet before write. Encryption key lives in Replit Secrets. This means the database file alone is worthless without the key.

---

## What To Do Next

1. Create Plaid developer account at dashboard.plaid.com
2. Generate encryption key: `python scripts/generate_key.py`
3. Add all secrets to Replit Secrets panel (see SETUP.md)
4. Deploy to Replit and run `bash run.sh`
5. Link accounts via the "Link account" page in the dashboard
6. Test Fidelity OFX connection — may need PIN separate from web password (see SETUP.md)

---

## Gotchas / Non-Obvious Things

- **Plaid sandbox vs development**: Sandbox uses fake data. Switch `PLAID_ENV=development` to connect real accounts. Development mode has a 100-item limit (more than enough for personal use).
- **Fidelity OFX PIN**: Some Fidelity users have a separate OFX/Quicken PIN. If your regular password doesn't work, call Fidelity (800-343-3548) and ask to enable "Quicken Direct Connect" — they'll either confirm your password works or issue a Direct Connect PIN.
- **Plaid credit card balances**: Plaid returns the current balance owed on credit cards as a positive number. The Overview page subtracts credit balances from net worth automatically (see `CREDIT_TYPES` in Overview.tsx).
- **Vite proxy**: In dev, Vite proxies `/api` → `http://localhost:8000`. In production, the frontend is served as static files and the backend serves `/api` on the same origin.
- **Database file**: `finance.db` contains your actual transaction data. It's git-ignored. Back it up manually or let Replit handle persistence.
- **Port mapping on Replit**: FastAPI is on port 8000, React dev server on 5173. The `.replit` file maps 5173 to port 80 (public-facing URL). Both are accessible externally.