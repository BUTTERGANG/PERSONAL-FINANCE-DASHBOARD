# Personal Finance Dashboard

A self-hosted finance dashboard that unifies your accounts into a single interface. Data comes in two ways: **document upload** (CSV exports and PDF bank statements — works today, no third-party approval needed) and **live sync** via Plaid + Fidelity OFX (once API access is granted).

**Stack:** FastAPI · SQLite · Plaid · OFX Direct Connect · **React + Vite + Recharts**

**Hosted on:** Replit (Always On)

> **Current data path: document upload.** Plaid developer access is still pending
> approval, so the live-sync connectors are built but dormant. In the meantime the
> dashboard is fully usable by creating **manual accounts** and importing **CSV** or
> **PDF** statements on the **Import** page — everything (net worth, spending,
> budgets, subscriptions, trends) works off imported data. See
> [ROADMAP.md](THE-VISION/ROADMAP.md) for the current focus.

---

## Quick Start

See **[THE-VISION/SETUP.md](THE-VISION/SETUP.md)** for the full setup guide.

The short version:
1. Add secrets to Replit Secrets panel (encryption key required; Plaid/Fidelity optional until access is granted)
2. `bash run.sh` — starts FastAPI on :8000 and Vite (React) on :5173
3. Add data one of two ways:
   - **Now (no approval needed):** create a manual account, then import CSV/PDF statements on the **Import** page
   - **Later (once Plaid is approved):** link banks via the **Link account** page

---

## Documentation

All documentation lives in `THE-VISION/`:

| File | Contents |
|------|---------|
| [SESSION-HANDOFF.md](THE-VISION/SESSION-HANDOFF.md) | Read first in every new Claude session |
| [ARCHITECTURE.md](THE-VISION/ARCHITECTURE.md) | System design, data flow, DB schema, API endpoints |
| [SETUP.md](THE-VISION/SETUP.md) | Step-by-step setup from zero to running |
| [SECURITY.md](THE-VISION/SECURITY.md) | Threat model, what's encrypted, what's safe to commit |
| [ROADMAP.md](THE-VISION/ROADMAP.md) | MVP done, Phase 2/3 backlog |
| [GITHUB-SETUP.md](THE-VISION/GITHUB-SETUP.md) | Private repo setup and granular access control |

---

## Project Structure

```
backend/           FastAPI app, Plaid client, OFX client, sync engine, PDF statement parser
react-frontend/    React + Vite + Recharts dashboard (all 8 pages built)
frontend/          OLD: Streamlit dashboard (superseded by react-frontend/, kept for reference)
THE-VISION/        Documentation
scripts/           generate_key.py, pre-commit hook
.env.example       Template for environment variables (copy to .env locally)
requirements.txt   Python dependencies
run.sh             Startup script for Replit
```

---

## Current Status

| Layer | Status |
|-------|--------|
| Backend API | ✅ Complete |
| Database models | ✅ Complete |
| Document import (CSV + PDF) | ✅ Complete — **primary data path** |
| Manual accounts | ✅ Complete |
| Plaid integration | ✅ Built — ⬜ dormant (dev access pending approval) |
| Fidelity OFX | ✅ Built — ⬜ needs real credentials |
| Encryption (Plaid tokens) | ✅ Complete |
| Auto-sync scheduler | ✅ Complete |
| **React frontend** | **✅ All 8 pages built** |
| Deployed to Replit | ⬜ Pending |
| Live accounts linked | ⬜ Blocked on Plaid approval |

All eight React pages are built: **Overview, Transactions, Accounts, Budgets, Subscriptions, Import, Link Account, Settings.**

### Getting data in — document upload

Because Plaid access is still pending, the **Import** page is how you populate the
dashboard today:

- **CSV import** — a sequential multi-file wizard: drop one or more bank CSVs, map the
  date/amount/description columns (auto-guessed), optionally flip amount signs, preview,
  and import. Re-importing the same file is idempotent (content-hashed row ids).
- **PDF statement import** — upload a bank statement PDF; the server parses it
  (auto-detects Chase, Citi, Bank of America, Wells Fargo, Discover, Amex, Capital One,
  US Bank, with generic table/text fallbacks), shows a preview, and imports on confirm.
- **Manual accounts** — create checking/savings/credit/investment/loan/asset/cash
  accounts by hand and set balances; they flow into net worth automatically.

Imported transactions carry a `source` of `csv` or `pdf` and feed every downstream
feature (spending charts, budgets, subscription detection, net worth trend).

---

## Security

- Plaid access tokens encrypted at rest (Fernet AES-128)
- No credentials stored in code or git history
- All secrets in Replit Secrets / environment variables
- Plaid connections are **read-only** — no transfer capability
- Uploaded PDFs are parsed in a temp file that is deleted immediately after parsing — the PDF itself is never persisted

> ⚠️ **Known gap:** neither the React UI nor the FastAPI backend currently has an
> access gate, and `.replit` exposes port 8000 publicly. Harden auth before deploying
> to a public Replit URL. See [SECURITY.md](THE-VISION/SECURITY.md).

See [THE-VISION/SECURITY.md](THE-VISION/SECURITY.md) for the full model.