"""
Subscriptions page — auto-detected recurring charges and their monthly/annual cost.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st

from utils.api import get_subscriptions, ignore_subscription
from utils.auth import require_pin

st.set_page_config(page_title="Subscriptions", page_icon="🔁", layout="wide")
require_pin()

st.markdown("""
<style>
  .stApp { background-color: #0f0f14; }
  [data-testid="metric-container"] { background: #1a1a24; border: 1px solid #2d2d3d; border-radius: 12px; padding: 16px 20px; }
  .stButton > button { background: #7c3aed; color: white; border: none; border-radius: 8px; }
  .stButton > button:hover { background: #6d28d9; border: none; }
  footer { visibility: hidden; } #MainMenu { visibility: hidden; }
</style>""", unsafe_allow_html=True)

st.title("🔁 Subscriptions")
st.caption("Recurring charges detected from the last 180 days. Hide anything that isn't a real subscription.")

subs = get_subscriptions()
if not subs:
    st.info("No recurring charges detected yet. This fills in once a few months of transactions are synced.")
    st.stop()

# ── Totals ────────────────────────────────────────────────────────────────────
total_monthly = sum(s["monthly_cost"] for s in subs)
total_annual = sum(s["est_annual"] for s in subs)
m1, m2, m3 = st.columns(3)
m1.metric("🔁 Active Subscriptions", f"{len(subs)}")
m2.metric("📅 Est. Monthly Cost", f"${total_monthly:,.2f}")
m3.metric("🗓️ Est. Annual Cost", f"${total_annual:,.2f}")

st.markdown("---")

# ── Detected list ─────────────────────────────────────────────────────────────
for s in subs:
    info, action = st.columns([6, 1])
    with info:
        # \$ prevents Streamlit's markdown from treating $...$ pairs as LaTeX math
        st.markdown(
            f"**{s['merchant'].title()}** &nbsp;·&nbsp; \\${s['amount']:,.2f} {s['frequency']} "
            f"&nbsp;·&nbsp; {s['category']}",
            unsafe_allow_html=True,
        )
        st.caption(
            f"~\\${s['monthly_cost']:,.2f}/mo · \\${s['est_annual']:,.2f}/yr · "
            f"seen {s['occurrences']}× · last {s['last_date']}"
        )
    with action:
        if st.button("🙈 Hide", key=f"ign_{s['merchant_key']}", help="Not a subscription — hide it"):
            ignore_subscription(s["merchant_key"])
            st.rerun()
