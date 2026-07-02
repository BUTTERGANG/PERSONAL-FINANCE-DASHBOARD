# Personal Finance Dashboard

A self-hosted finance dashboard pulling live data from Fidelity, Chase, Citi, PayPal, and Venmo into a unified interface.

**Stack:** FastAPI · SQLite · Plaid · OFX Direct Connect · **React + Vite + Recharts**

**Hosted on:** Replit (Always On)

---

## Quick Start

See **[THE-VISION/SETUP.md](THE-VISION/SETUP.md)** for the full setup guide.

The short version:
1. Add secrets to Replit Secrets panel (Plaid keys, Fidelity credentials, encryption key)
2. `bash run.sh` — starts FastAPI on :8000 and Vite (React) on :5173
3. Link accounts via the **Link account** page in the dashboard

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
backend/           FastAPI app, Plaid client, OFX client, sync engine
react-frontend/    React + Vite + Recharts dashboard (Overview complete, 7 pages scaffolded)
frontend/          OLD: Streamlit dashboard (kept for reference)
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
| Plaid integration | ✅ Complete |
| Fidelity OFX | ✅ Complete |
| Encryption | ✅ Complete |
| Auto-sync scheduler | ✅ Complete |
| **React frontend (Phase 1)** | **✅ Overview page complete** |
| Deployed to Replit | ⬜ Pending |
| Real accounts linked | ⬜ Pending |

The **Overview page** is fully built with:
- Net worth, assets, debt, 30-day spend metric cards
- Net worth trend chart (area chart, 180 days)
- Month-over-month spending comparison (top 4 movers)
- Account balance list with institution badges
- Budget alerts banner (warning/danger thresholds)
- Dark/light theme toggle

The remaining 7 pages (Transactions, Accounts, Budgets, Subscriptions, Import, Link Account, Settings) are scaffolded as placeholders — ready for Phase 2 implementation.

---

## Security

- Plaid access tokens encrypted at rest (Fernet AES-128)
- No credentials stored in code or git history
- All secrets in Replit Secrets / environment variables
- Plaid connections are **read-only** — no transfer capability

See [THE-VISION/SECURITY.md](THE-VISION/SECURITY.md) for the full model.