"""
Budgets page — set a monthly spending limit per category and track progress.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from utils.api import delete_budget, get_budgets, get_categories, set_budget
from utils.auth import require_pin

st.set_page_config(page_title="Budgets", page_icon="🎯", layout="wide")
require_pin()

st.markdown("""
<style>
  .stApp { background-color: #0f0f14; }
  [data-testid="metric-container"] { background: #1a1a24; border: 1px solid #2d2d3d; border-radius: 12px; padding: 16px 20px; }
  .stButton > button { background: #7c3aed; color: white; border: none; border-radius: 8px; }
  .stButton > button:hover { background: #6d28d9; border: none; }
  footer { visibility: hidden; } #MainMenu { visibility: hidden; }
</style>""", unsafe_allow_html=True)

st.title("🎯 Budgets")
st.caption("Monthly spending limits by category. Progress resets on the 1st of each month.")

# ── Add / edit a budget ───────────────────────────────────────────────────────
categories = get_categories()
with st.form("add_budget", clear_on_submit=True):
    st.subheader("Set a budget")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        if categories:
            category = st.selectbox("Category", categories)
        else:
            category = st.text_input("Category", placeholder="e.g. Food and Drink")
    with c2:
        limit_amount = st.number_input("Monthly limit ($)", min_value=1.0, step=25.0, value=200.0)
    with c3:
        st.write("")
        st.write("")
        submitted = st.form_submit_button("💾 Save")
    if submitted and category:
        set_budget(category, float(limit_amount))
        st.success(f"Budget set: {category} → ${limit_amount:,.0f}/mo")
        st.rerun()

st.markdown("---")

# ── Current budgets ───────────────────────────────────────────────────────────
budgets = get_budgets()
if not budgets:
    st.info("No budgets yet. Set one above to start tracking a category.")
    st.stop()

for b in budgets:
    spent, limit, pct = b["spent"], b["limit_amount"], b["pct"]
    over = spent > limit

    row, btn = st.columns([6, 1])
    with row:
        # \$ prevents Streamlit's markdown from treating $...$ pairs as LaTeX math
        label = f"**{b['category']}** — \\${spent:,.2f} / \\${limit:,.2f}"
        if over:
            st.markdown(f"🔴 {label} &nbsp; · &nbsp; **\\${abs(b['remaining']):,.2f} over**", unsafe_allow_html=True)
        else:
            st.markdown(f"🟢 {label} &nbsp; · &nbsp; \\${b['remaining']:,.2f} left", unsafe_allow_html=True)
        st.progress(min(pct / 100, 1.0), text=f"{pct:.0f}% of budget")
    with btn:
        st.write("")
        if st.button("🗑️", key=f"del_{b['category']}", help="Delete this budget"):
            delete_budget(b["category"])
            st.rerun()
