# Session Handoff — Personal Finance Dashboard

> Read this first at the start of every new Claude session.
> It gives you full context without needing to re-read code.

---

## What We're Building

A self-hosted personal finance dashboard running on Replit that unifies five accounts — Fidelity (investment), Chase (checking), Citi (credit card), PayPal, and Venmo — into a single SQLite database, and presents net worth, spending by category, transaction history, and balance trends.

**Design principle:** Zero daily friction.

> ⚠️ **CURRENT REALITY (read before planning work): Plaid developer API access has
> not been granted yet** — the approval request is still pending. The Plaid + Fidelity
> live-sync connectors are fully built but **dormant** (no credentials). The working
> data path today is **document upload**: create manual accounts, then import **CSV**
> or **PDF** bank statements on the Import page. All dashboard features run off imported
> data. **Focus new work on the document-upload experience**, not live sync.

---

## Architecture in One Paragraph

**FastAPI** backend (port 8000) handles all data ingestion and storage; everything lands in **SQLite** (`finance.db`). Data enters two ways. **Today (working): document upload** — the Import page creates manual accounts and imports CSV rows and parsed PDF statements via `/api/manual/*`. **When Plaid access is granted (dormant): live sync** — **Plaid** for Chase/Citi/PayPal/Venmo (OAuth, no stored passwords, 2FA handled) and **OFX direct connect** for Fidelity, with Plaid tokens Fernet-encrypted at rest and an **APScheduler** job syncing every 4 hours. The **React + Recharts** frontend (port 5173 via Vite dev, static assets in prod) calls the FastAPI REST endpoints and renders interactive charts. Both data paths write the same `transactions` table, so the dashboard is identical regardless of source.

---

## File Map — Where Things Live

```
backend/
  config.py           ← All env var settings (pydantic-settings)
  models.py           ← SQLAlchemy: Account, Transaction, SyncLog, Budget, NetWorthSnapshot, IgnoredSubscription
  database.py         ← Engine setup, get_db() dependency
  crypto.py           ← Fernet encrypt/decrypt for token storage
  plaid_client.py     ← Link token creation, token exchange, balance/txn fetch (dormant — no Plaid access yet)
  fidelity_client.py  ← OFX direct connect to Fidelity (dormant — no credentials yet)
  pdf_parser.py       ← Section-aware, self-reconciling PDF statement parser. 6 tuned
                        (bank, product) types: Chase checking; Citi/PayPal/Venmo credit;
                        Fidelity brokerage + crypto (holdings). Reconciles parsed sums vs
                        printed totals; extracts summary balances + investment holdings.
                        Legacy line-regex fallback for unrecognized statements.
  sync.py             ← Orchestrates all account syncs
  main.py             ← FastAPI app, CORS, scheduler startup
  api/
    accounts.py       ← GET /api/accounts/
    transactions.py   ← GET /api/transactions/, /summary, /mom, /categories
    plaid_routes.py   ← GET /api/plaid/link, POST /api/plaid/exchange (dormant)
    sync_routes.py    ← POST /api/sync/trigger, GET /api/sync/logs
    networth.py       ← GET /api/networth/snapshots
    budgets.py        ← GET /api/budgets/, /alerts, POST/DELETE /budgets/
    subscriptions.py  ← GET /api/subscriptions/, POST/DELETE /ignore
    manual.py         ← Manual accounts + IMPORT (primary data path):
                        POST /manual/accounts, PATCH /manual/accounts/:id,
                        POST /manual/import (CSV rows),
                        POST /manual/import-pdf/preview (parse, no save),
                        POST /manual/import-pdf/confirm (save parsed rows)

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
    pages/            ← ALL 8 pages built (each has its own .css)
      Overview.tsx     ← Net worth, assets/debt, spending, net worth trend, MoM movers, accounts list
      Transactions.tsx ← Filterable table (date/account/category/search)
      Accounts.tsx     ← Balance cards, sync status, manual account create/edit
      Budgets.tsx      ← Budget list, progress bars, create/edit
      Subscriptions.tsx← Detected recurring list, dismiss/restore
      Import.tsx       ← ★ CSV multi-file wizard + PDF statement upload (preview→confirm) — the data path
      LinkAccount.tsx  ← Opens server-rendered Plaid Link page + Fidelity OFX setup (dormant until Plaid access)
      Settings.tsx     ← Sync trigger, sync logs, CSV export
      Placeholder.tsx  ← Legacy stub component, no longer routed to
    theme/
      theme.css        ← CSS variables design system (light/dark, tokens)
      colors.ts        ← Runtime chart color accessor (reads CSS vars)
    components.css     ← Shared component styles (cards, tables, badges, buttons, inputs, spinner, empty state)

frontend/             REMOVED 2026-09-15: legacy Streamlit dashboard (superseded by react-frontend/; it crashed the server on Transactions, so it was retired)
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
| **Document import (CSV + PDF)** | **✅ Built — primary data path** | Manual accounts + CSV wizard + PDF statement parse/preview/confirm |
| Plaid integration | ✅ Built — ⬜ **dormant** | Code complete; **blocked on Plaid dev access approval** |
| Fidelity OFX | ✅ Built — ⬜ dormant | Needs real credentials |
| Encryption (Plaid tokens) | ✅ Built | Fernet, key from env var |
| Auto-sync scheduler | ✅ Built | APScheduler, configurable interval (only matters once live sync is active) |
| **React frontend** | **✅ All 8 pages built** | Overview, Transactions, Accounts, Budgets, Subscriptions, Import, LinkAccount, Settings |
| Access control (UI + API) | ⬜ **Missing** | No PIN gate on React, no auth on backend, port 8000 public — harden before deploy |
| Deployed to Replit | ⬜ Pending | See SETUP.md for deployment steps |
| Live accounts linked | ⬜ Blocked | Waiting on Plaid approval + Fidelity credentials |

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

**Plaid is blocked, so the near-term work is document upload + hardening — not linking.**

The PDF import pipeline is now solid: 6 statement types tuned + reconciling (45 tests),
the Import preview shows reconciliation status / summary balances / holdings, and confirm
can sync the account balance (and import holdings-only Fidelity statements). Remaining:

1. **Post-import categorization** — imported rows have no category, so budgets/spending
   charts stay thin until this exists. Highest-value functional gap. Needs a
   `PATCH /transactions/{id}` (category) endpoint — not built yet.
2. **Persist holdings** — Fidelity holdings are parsed + shown but not stored. A
   `Holding` table + a portfolio view would make them durable.
3. **More statement types** — Discover, Amex, etc. as samples arrive. Each is a
   declarative `StatementType` config in `pdf_parser.py` + a fixture in
   `tests/fixtures/statements/` + a `Case`/test. Follow the existing 6 as templates.
4. **Optional**: accept `.ofx`/`.qfx` uploads (structured; complements PDF).
5. Deploy to Replit and run `bash run.sh` (works today with document upload only).

> Auth is already done (PIN gate on all `/api/*` both ends) — no longer a blocker.

**Parked until Plaid access is granted:**
- Create Plaid developer account at dashboard.plaid.com, add secrets, link via "Link account"
- Test Fidelity OFX connection — may need a PIN separate from web password (see SETUP.md)

Encryption key is still needed regardless: `python scripts/generate_key.py` → Replit Secrets.

---

## Gotchas / Non-Obvious Things

- **Plaid sandbox vs development**: Sandbox uses fake data. Switch `PLAID_ENV=development` to connect real accounts. Development mode has a 100-item limit (more than enough for personal use).
- **Fidelity OFX PIN**: Some Fidelity users have a separate OFX/Quicken PIN. If your regular password doesn't work, call Fidelity (800-343-3548) and ask to enable "Quicken Direct Connect" — they'll either confirm your password works or issue a Direct Connect PIN.
- **Plaid credit card balances**: Plaid returns the current balance owed on credit cards as a positive number. The Overview page subtracts credit balances from net worth automatically (see `CREDIT_TYPES` in Overview.tsx).
- **Vite proxy**: In dev, Vite proxies `/api` → `http://localhost:8000`. In production, the frontend is served as static files and the backend serves `/api` on the same origin.
- **Database file**: `finance.db` contains your actual transaction data. It's git-ignored. Back it up manually or let Replit handle persistence.
- **Port mapping on Replit**: FastAPI is on port 8000, React dev server on 5173. The `.replit` file maps 5173 to port 80 (public-facing URL). Both are accessible externally.