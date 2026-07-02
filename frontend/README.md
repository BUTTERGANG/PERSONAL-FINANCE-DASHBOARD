# Legacy Streamlit Frontend (Deprecated)

This directory contains the original Streamlit-based dashboard.

**Status:** Deprecated — kept for reference only. The production frontend is now in `react-frontend/`.

## Pages (Streamlit)
- `1_Overview.py` — Net worth, spending charts, account cards
- `2_Transactions.py` — Filterable transaction table
- `3_Accounts.py` — Account management, sync status
- `4_Link_Account.py` — Plaid Link flow, Fidelity OFX setup
- `5_Settings.py` — Sync config, data export, sync logs

## To Run (Not Recommended)
```bash
streamlit run frontend/app.py --server.port 8501
```

See `THE-VISION/ROADMAP.md` for the React frontend migration status.