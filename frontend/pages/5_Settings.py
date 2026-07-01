"""
Settings page — sync configuration, sync logs, data export, and health check.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime

import pandas as pd
import streamlit as st

from utils.api import get_accounts, get_sync_logs, get_transactions, trigger_sync, trigger_sync_realtime
from utils.auth import require_pin

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
require_pin()
st.markdown("""
<style>
  .stApp { background-color: #0f0f14; }
  [data-testid="metric-container"] { background: #1a1a24; border: 1px solid #2d2d3d; border-radius: 12px; padding: 16px 20px; }
  .stButton > button { background: #7c3aed; color: white; border: none; border-radius: 8px; }
  footer { visibility: hidden; } #MainMenu { visibility: hidden; }
</style>""", unsafe_allow_html=True)

st.title("⚙️ Settings")

# ── Sync controls ─────────────────────────────────────────────────────────────
st.subheader("Sync Configuration")
st.info(
    "Sync interval is set via the `SYNC_INTERVAL_HOURS` environment variable in Replit Secrets. "
    "Default is every 4 hours."
)

col1, col2 = st.columns([1, 1])
with col1:
    st.markdown("**Live Balance Sync** — fetches real-time balances from your bank ($0.10/account via Plaid Balance product)")
    if st.button("⚡ Sync Now (Live Balances)"):
        with st.spinner("Fetching live balances + transactions... this takes ~15s"):
            result = trigger_sync_realtime()
        if result.get("status") == "completed":
            errors = result.get("errors", [])
            plaid_results = result.get("plaid", {})
            if plaid_results:
                summary = ", ".join(f"{inst}: +{n} txns" for inst, n in plaid_results.items())
                st.success(f"✅ Sync complete — {summary}. Balances are live as of right now.")
            if errors:
                for err in errors:
                    st.warning(f"⚠️ {err}")
        else:
            st.info(str(result))

with col2:
    if st.button("♻️ Clear Cache"):
        from utils.api import get_accounts, get_categories, get_spending_summary, get_sync_logs, get_transactions
        get_accounts.clear()
        get_transactions.clear()
        get_spending_summary.clear()
        get_sync_logs.clear()
        get_categories.clear()
        st.success("Cache cleared. Next page load will fetch fresh data.")

st.markdown("---")

# ── Sync logs ─────────────────────────────────────────────────────────────────
st.subheader("Sync History")
logs = get_sync_logs()
if logs:
    df_logs = pd.DataFrame(logs)
    if "synced_at" in df_logs.columns:
        df_logs["synced_at"] = pd.to_datetime(df_logs["synced_at"], errors="coerce")
        df_logs["synced_at"] = df_logs["synced_at"].dt.strftime("%Y-%m-%d %I:%M %p")
    cols_show = [c for c in ["synced_at", "institution", "status", "transactions_added", "error_message"] if c in df_logs.columns]
    rename = {
        "synced_at": "Time", "institution": "Institution",
        "status": "Status", "transactions_added": "Added",
        "error_message": "Error",
    }
    st.dataframe(df_logs[cols_show].rename(columns=rename), use_container_width=True, hide_index=True)
else:
    st.info("No sync history yet.")

st.markdown("---")

# ── Data Export ───────────────────────────────────────────────────────────────
st.subheader("Export Data")
st.markdown("Download your transaction history as CSV files.")

col_e1, col_e2 = st.columns(2)

with col_e1:
    if st.button("📥 Export Last 30 Days"):
        txns = get_transactions(days=30)
        if txns:
            df = pd.DataFrame(txns)
            csv = df.to_csv(index=False)
            st.download_button(
                "⬇️ Download CSV",
                data=csv,
                file_name="transactions_30d.csv",
                mime="text/csv",
                key="dl_30",
            )
        else:
            st.warning("No transactions to export.")

with col_e2:
    if st.button("📥 Export Last 365 Days"):
        txns = get_transactions(days=365)
        if txns:
            df = pd.DataFrame(txns)
            csv = df.to_csv(index=False)
            st.download_button(
                "⬇️ Download CSV",
                data=csv,
                file_name="transactions_365d.csv",
                mime="text/csv",
                key="dl_365",
            )
        else:
            st.warning("No transactions to export.")

st.markdown("---")

# ── Health check ──────────────────────────────────────────────────────────────
st.subheader("System Status")

import httpx, os
backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")

try:
    r = httpx.get(f"{backend_url}/health", timeout=5)
    health = r.json()
    st.success(f"✅ Backend API is healthy — sync interval: every {health.get('sync_interval_hours', '?')} hours")
except Exception as exc:
    st.error(f"❌ Backend API is not responding: {exc}")

accounts = get_accounts()
st.info(f"📊 {len(accounts)} account(s) linked across {len({a['institution'] for a in accounts})} institution(s).")

# ── About ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("About")
st.markdown("""
**Personal Finance Dashboard** — built with FastAPI + Streamlit + Plaid + OFX.

- 📄 Architecture: `THE-VISION/ARCHITECTURE.md`
- 🔐 Security model: `THE-VISION/SECURITY.md`
- 🗺️ Roadmap: `THE-VISION/ROADMAP.md`
- 🔄 Session handoff (for Claude): `THE-VISION/SESSION-HANDOFF.md`
""")
