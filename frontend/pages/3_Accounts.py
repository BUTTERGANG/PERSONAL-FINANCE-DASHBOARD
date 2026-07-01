"""
Accounts page — shows linked accounts with balance details and sync status.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone

import streamlit as st

from utils.api import get_accounts, get_sync_logs, trigger_sync
from utils.auth import require_pin

st.set_page_config(page_title="Accounts", page_icon="🏦", layout="wide")
require_pin()
st.markdown("""
<style>
  .stApp { background-color: #0f0f14; }
  [data-testid="metric-container"] { background: #1a1a24; border: 1px solid #2d2d3d; border-radius: 12px; padding: 16px 20px; }
  .stButton > button { background: #7c3aed; color: white; border: none; border-radius: 8px; }
  footer { visibility: hidden; } #MainMenu { visibility: hidden; }
  .account-card {
    background: #1a1a24; border: 1px solid #2d2d3d; border-radius: 14px;
    padding: 20px 24px; margin-bottom: 16px;
  }
</style>""", unsafe_allow_html=True)

INST_META = {
    "chase":    {"icon": "🏦", "full": "JPMorgan Chase", "color": "#1a56db"},
    "citi":     {"icon": "💳", "full": "Citibank",       "color": "#e3342f"},
    "fidelity": {"icon": "📈", "full": "Fidelity",       "color": "#22c55e"},
    "paypal":   {"icon": "🅿️", "full": "PayPal",         "color": "#003087"},
    "venmo":    {"icon": "💬", "full": "Venmo",          "color": "#008CFF"},
}

st.title("🏦 Linked Accounts")

# ── Sync controls ─────────────────────────────────────────────────────────────
col_hdr, col_btn = st.columns([4, 1])
with col_btn:
    if st.button("🔄 Sync All Now"):
        with st.spinner("Syncing..."):
            trigger_sync()
        st.success("Sync started.")
        st.rerun()

accounts = get_accounts()

if not accounts:
    st.info("No accounts linked yet. Go to **Link Account** to connect your first bank.")
    st.stop()

# ── Account cards ─────────────────────────────────────────────────────────────
st.markdown("---")

for acct in accounts:
    inst_key = acct["institution"].split("_")[0]
    meta = INST_META.get(inst_key, {"icon": "🏛️", "full": acct["institution"].title(), "color": "#6b7280"})
    is_credit = acct["account_type"] == "credit"

    last_synced = acct.get("last_synced")
    if last_synced:
        if isinstance(last_synced, str):
            last_synced = datetime.fromisoformat(last_synced.replace("Z", "+00:00"))
        synced_str = last_synced.strftime("%b %d, %Y at %I:%M %p UTC")
    else:
        synced_str = "Never synced"

    balance = acct["balance"]
    balance_display = f"-${balance:,.2f}" if is_credit else f"${balance:,.2f}"

    col_info, col_bal = st.columns([3, 1])
    with col_info:
        st.markdown(f"""
<div class="account-card">
  <div style="font-size:1.1rem;font-weight:600;margin-bottom:4px;">
    {meta['icon']} {acct['name']}
  </div>
  <div style="color:#94a3b8;font-size:0.85rem;">
    {meta['full']} &nbsp;·&nbsp; {acct['account_type'].title()} &nbsp;·&nbsp; {acct.get('currency','USD')}
  </div>
  <div style="color:#64748b;font-size:0.78rem;margin-top:8px;">
    🕐 Last synced: {synced_str}
  </div>
</div>
""", unsafe_allow_html=True)

    with col_bal:
        color = "#ef4444" if is_credit else "#22c55e"
        st.markdown(f"""
<div style="background:#1a1a24;border:1px solid #2d2d3d;border-radius:14px;
            padding:20px 24px;text-align:right;height:100%;">
  <div style="color:#94a3b8;font-size:0.8rem;">Current Balance</div>
  <div style="font-size:1.6rem;font-weight:700;color:{color};">{balance_display}</div>
  {"<div style='color:#94a3b8;font-size:0.78rem;'>Amount owed</div>" if is_credit else ""}
</div>
""", unsafe_allow_html=True)

# ── Sync logs ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Recent Sync Activity")

logs = get_sync_logs()
if logs:
    for log in logs[:10]:
        synced_at = log.get("synced_at", "")
        if isinstance(synced_at, str) and synced_at:
            try:
                synced_at = datetime.fromisoformat(synced_at.replace("Z", "+00:00")).strftime("%b %d %I:%M %p")
            except Exception:
                pass

        if log["status"] == "success":
            st.success(
                f"✅ {log['institution'].title()} — {log['transactions_added']} new transactions — {synced_at}"
            )
        else:
            st.error(
                f"❌ {log['institution'].title()} — Error: {log.get('error_message', 'Unknown')} — {synced_at}"
            )
else:
    st.info("No sync history yet.")
