"""
Link Account page — Plaid Link for Chase/Citi/PayPal/Venmo + Fidelity OFX status.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from utils.api import get_accounts, get_plaid_link_url
from utils.auth import require_pin

st.set_page_config(page_title="Link Account", page_icon="🔗", layout="wide")
require_pin()
st.markdown("""
<style>
  .stApp { background-color: #0f0f14; }
  .stButton > button { background: #7c3aed; color: white; border: none; border-radius: 8px; font-size: 1rem; padding: 0.6rem 1.5rem; }
  .stButton > button:hover { background: #6d28d9; border: none; }
  footer { visibility: hidden; } #MainMenu { visibility: hidden; }
  .info-card {
    background: #1a1a24; border: 1px solid #2d2d3d; border-radius: 14px;
    padding: 20px 24px; margin-bottom: 16px;
  }
</style>""", unsafe_allow_html=True)

st.title("🔗 Link Account")
st.markdown("Connect your financial accounts. You only do this once per institution.")

accounts = get_accounts()
linked_institutions = {a["institution"].split("_")[0] for a in accounts}
plaid_link_url = get_plaid_link_url()

st.markdown("---")

# ── Plaid institutions ────────────────────────────────────────────────────────
st.subheader("Connect via Plaid")
st.caption("Plaid handles authentication and 2FA. Your bank credentials never touch our servers.")

plaid_institutions = [
    {"key": "chase",  "name": "Chase",  "icon": "🏦", "type": "Checking / Savings"},
    {"key": "citi",   "name": "Citi",   "icon": "💳", "type": "Credit Card"},
    {"key": "paypal", "name": "PayPal", "icon": "🅿️", "type": "Digital Wallet"},
    {"key": "venmo",  "name": "Venmo",  "icon": "💬", "type": "Digital Wallet"},
]

cols = st.columns(2)
for i, inst in enumerate(plaid_institutions):
    is_linked = inst["key"] in linked_institutions
    with cols[i % 2]:
        status_badge = "✅ Connected" if is_linked else "⬜ Not linked"
        st.markdown(f"""
<div class="info-card">
  <div style="font-size:1.1rem;font-weight:600;">{inst['icon']} {inst['name']}</div>
  <div style="color:#94a3b8;font-size:0.85rem;margin-bottom:12px;">{inst['type']}</div>
  <div style="font-size:0.85rem;color:{'#22c55e' if is_linked else '#94a3b8'};">{status_badge}</div>
</div>
""", unsafe_allow_html=True)

st.markdown("**Click the button below** to open the Plaid Link flow in a new tab.")
st.markdown("Select your institution inside Plaid, complete authentication, then return here and click Refresh.")

col_btn, col_refresh = st.columns([1, 1])
with col_btn:
    st.link_button("🔗 Open Plaid Link", plaid_link_url)
with col_refresh:
    if st.button("🔄 Refresh Account List"):
        from utils.api import get_accounts
        get_accounts.clear()
        st.rerun()

st.markdown("---")

# ── Fidelity OFX ─────────────────────────────────────────────────────────────
st.subheader("📈 Fidelity (Investment Account)")
st.markdown("""
Fidelity connects via **OFX Direct Connect** — the same protocol used by Quicken.
No Plaid Link required. No 2FA per pull. Configured once via Replit Secrets.
""")

is_fidelity_linked = "fidelity" in linked_institutions
fid_status_color = "#22c55e" if is_fidelity_linked else "#f59e0b"
fid_status = "✅ Connected and syncing" if is_fidelity_linked else "⚠️ Not yet configured"

st.markdown(f"""
<div class="info-card">
  <div style="font-size:1.1rem;font-weight:600;">📈 Fidelity Investments</div>
  <div style="color:#94a3b8;font-size:0.85rem;margin-bottom:12px;">Brokerage / Investment Account</div>
  <div style="color:{fid_status_color};font-size:0.9rem;">{fid_status}</div>
</div>
""", unsafe_allow_html=True)

if not is_fidelity_linked:
    with st.expander("How to set up Fidelity OFX"):
        st.markdown("""
**Step 1:** Make sure these are set in Replit Secrets:
- `FIDELITY_USER` — your Fidelity username
- `FIDELITY_PIN` — your Fidelity password (may need a separate Direct Connect PIN)
- `FIDELITY_ACCOUNT_ID` — your 9-digit Fidelity account number

**Step 2:** After setting secrets, restart the app (click Stop → Run in Replit).

**Step 3:** Click **Sync All Now** on the Accounts page. If Fidelity is configured,
it will appear in the sync logs.

**If it fails with an auth error:**
Call Fidelity at 800-343-3548 and ask to enable "Quicken Direct Connect."
They will confirm whether your regular password works or issue a Direct Connect PIN.
See also: THE-VISION/SECURITY.md → Troubleshooting Fidelity OFX
""")

st.markdown("---")

# ── Linked account summary ────────────────────────────────────────────────────
if accounts:
    st.subheader("Currently Linked Accounts")
    for acct in accounts:
        st.markdown(f"- **{acct['name']}** ({acct['institution'].title()}) — {acct['account_type'].title()}")
