"""
Transactions page — filterable table, category breakdown, export.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.api import get_accounts, get_categories, get_transactions
from utils.auth import require_pin

st.set_page_config(page_title="Transactions", page_icon="💳", layout="wide")
require_pin()
st.markdown("""
<style>
  .stApp { background-color: #0f0f14; }
  [data-testid="metric-container"] { background: #1a1a24; border: 1px solid #2d2d3d; border-radius: 12px; padding: 16px 20px; }
  .stButton > button { background: #7c3aed; color: white; border: none; border-radius: 8px; }
  footer { visibility: hidden; } #MainMenu { visibility: hidden; }
</style>""", unsafe_allow_html=True)

st.title("💳 Transactions")

# ── Filters ───────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns([1, 1, 1, 2])

accounts = get_accounts()
categories = get_categories()

account_options = {"All Accounts": None} | {a["name"]: a["id"] for a in accounts}
category_options = ["All Categories"] + categories

with col1:
    days = st.selectbox("Period", [7, 30, 60, 90, 365], index=1, format_func=lambda d: f"Last {d} days")
with col2:
    acct_label = st.selectbox("Account", list(account_options.keys()))
    account_id = account_options[acct_label]
with col3:
    cat_label = st.selectbox("Category", category_options)
    category = None if cat_label == "All Categories" else cat_label
with col4:
    search = st.text_input("Search descriptions", placeholder="e.g. Amazon, Starbucks")

transactions = get_transactions(
    days=days,
    account_id=account_id,
    search=search or None,
    category=category,
)

# ── Summary metrics ───────────────────────────────────────────────────────────
if transactions:
    df = pd.DataFrame(transactions)
    df["date"] = pd.to_datetime(df["date"])
    df_spend = df[df["amount"] > 0]
    df_credit = df[df["amount"] < 0]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Transactions", len(df))
    m2.metric("Total Spent", f"${df_spend['amount'].sum():,.2f}")
    m3.metric("Total Credits / Refunds", f"${abs(df_credit['amount'].sum()):,.2f}")
    largest = df_spend["amount"].max() if not df_spend.empty else 0
    m4.metric("Largest Transaction", f"${largest:,.2f}")

    st.markdown("---")

    # ── Charts ────────────────────────────────────────────────────────────────
    chart_l, chart_r = st.columns(2)

    with chart_l:
        st.subheader("Spending by Category")
        cat_data = df_spend.groupby(df_spend["category"].fillna("Uncategorized"))["amount"].sum().reset_index()
        cat_data.columns = ["Category", "Amount"]
        cat_data = cat_data.sort_values("Amount", ascending=True).tail(10)
        fig = px.bar(
            cat_data, x="Amount", y="Category", orientation="h",
            color_discrete_sequence=["#7c3aed"],
        )
        fig.update_layout(
            paper_bgcolor="#1a1a24", plot_bgcolor="#1a1a24", font_color="#f1f5f9",
            margin=dict(t=10, b=10, l=10, r=10),
            xaxis=dict(showgrid=True, gridcolor="#2d2d3d"),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True)

    with chart_r:
        st.subheader("Spending Over Time")
        df_daily = df_spend.copy()
        df_daily["day"] = df_daily["date"].dt.date
        df_daily = df_daily.groupby("day")["amount"].sum().reset_index()
        fig2 = px.area(
            df_daily, x="day", y="amount",
            color_discrete_sequence=["#7c3aed"],
            labels={"amount": "Spent ($)", "day": "Date"},
        )
        fig2.update_layout(
            paper_bgcolor="#1a1a24", plot_bgcolor="#1a1a24", font_color="#f1f5f9",
            margin=dict(t=10, b=10, l=10, r=10),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#2d2d3d"),
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # ── Transaction table ─────────────────────────────────────────────────────
    st.subheader(f"All Transactions ({len(df)})")

    acct_id_to_name = {a["id"]: a["name"] for a in accounts}
    df_display = df.copy()
    df_display["Account"] = df_display["account_id"].map(acct_id_to_name).fillna(df_display["account_id"])
    df_display["date"] = df_display["date"].dt.strftime("%Y-%m-%d")
    df_display["Type"] = df_display["amount"].apply(lambda x: "💸 Debit" if x > 0 else "💰 Credit")
    df_display["amount"] = df_display["amount"].apply(
        lambda x: f"${x:,.2f}" if x > 0 else f"−${abs(x):,.2f}"
    )
    df_display["pending"] = df_display["pending"].apply(lambda x: "⏳ Pending" if x else "✅ Settled")

    cols_show = ["date", "description", "amount", "category", "Account", "Type", "pending", "source"]
    rename = {
        "date": "Date", "description": "Description", "amount": "Amount",
        "category": "Category", "pending": "Status", "source": "Source",
    }
    st.dataframe(
        df_display[cols_show].rename(columns=rename),
        use_container_width=True,
        hide_index=True,
    )

    # ── Export ────────────────────────────────────────────────────────────────
    csv = df_display[cols_show].rename(columns=rename).to_csv(index=False)
    st.download_button(
        "⬇️ Export as CSV",
        data=csv,
        file_name=f"transactions_{days}d.csv",
        mime="text/csv",
    )

else:
    st.info("No transactions found for the selected filters. Try syncing your accounts first.")
