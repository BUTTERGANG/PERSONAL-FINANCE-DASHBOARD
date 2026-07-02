"""
Overview page — Net worth, account balance cards, spending charts, recent transactions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.api import (
    get_accounts,
    get_budget_alerts,
    get_month_over_month,
    get_networth_snapshots,
    get_spending_summary,
    get_transactions,
    trigger_sync,
)
from utils.auth import require_pin
from utils.themes import get_color_palette, get_plotly_layout

st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")
require_pin()

# ── Institution colors & icons ────────────────────────────────────────────────
INST_META = {
    "chase":    {"icon": "🏦", "color": "#1a56db"},
    "citi":     {"icon": "💳", "color": "#e3342f"},
    "fidelity": {"icon": "📈", "color": "#22c55e"},
    "paypal":   {"icon": "🅿️", "color": "#003087"},
    "venmo":    {"icon": "💬", "color": "#008CFF"},
}
CREDIT_TYPES = {"credit"}


def calculate_net_worth(accounts: list[dict]) -> tuple[float, float, float]:
    assets = sum(a["balance"] for a in accounts if a["account_type"] not in CREDIT_TYPES)
    debts = sum(a["balance"] for a in accounts if a["account_type"] in CREDIT_TYPES)
    return assets - debts, assets, debts


# ── Header ────────────────────────────────────────────────────────────────────
col_title, col_sync = st.columns([4, 1])
with col_title:
    st.title("📊 Overview")
with col_sync:
    st.write("")
    if st.button("🔄 Sync Now"):
        with st.spinner("Syncing all accounts..."):
            trigger_sync()
        st.success("Sync started! Refresh in a moment.")
        st.rerun()

# ── Load data ─────────────────────────────────────────────────────────────────
accounts = get_accounts()
days_choice = st.selectbox("Period", [7, 30, 90], index=1, format_func=lambda d: f"Last {d} days")
transactions = get_transactions(days=days_choice)
summary = get_spending_summary(days=days_choice)

if not accounts:
    st.info("No accounts linked yet. Go to **Link Account** to connect your first bank.")
    st.stop()

# ── Net worth headline ────────────────────────────────────────────────────────
net_worth, total_assets, total_debt = calculate_net_worth(accounts)

st.markdown("---")
m1, m2, m3, m4 = st.columns(4)
m1.metric("💰 Net Worth", f"${net_worth:,.2f}")
m2.metric("📥 Total Assets", f"${total_assets:,.2f}")
m3.metric("📤 Total Debt", f"${total_debt:,.2f}")
total_spend = sum(t["amount"] for t in transactions if t["amount"] > 0 and not t["pending"])
m4.metric(f"🛒 Spent (last {days_choice}d)", f"${total_spend:,.2f}")

# ── Budget alerts ───────────────────────────────────────────────────────────────
alerts = get_budget_alerts()
if alerts:
    st.markdown("---")
    danger_alerts = [a for a in alerts if a["level"] == "danger"]
    warning_alerts = [a for a in alerts if a["level"] == "warning"]

    if danger_alerts:
        for a in danger_alerts:
            st.error(f"🔴 **{a['category']}**: {a['message']}", icon="🔴")

    if warning_alerts:
        for a in warning_alerts:
            st.warning(f"⚠️ **{a['category']}**: {a['message']}", icon="⚠️")

# ── Net worth trend ───────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Net Worth Trend")
snapshots = get_networth_snapshots(days=365)
if len(snapshots) >= 2:
    df_nw = pd.DataFrame(snapshots)
    df_nw["day"] = pd.to_datetime(df_nw["day"])
    fig_nw = px.line(
        df_nw,
        x="day",
        y="net_worth",
        markers=True,
        color_discrete_sequence=["#22c55e"],
        labels={"net_worth": "Net Worth ($)", "day": ""},
    )
    layout = get_plotly_layout()
    layout["xaxis"]["showgrid"] = True
    layout["xaxis"]["gridcolor"] = layout.get("yaxis", {}).get("gridcolor", "#2d2d3d")
    fig_nw.update_layout(**layout)
    st.plotly_chart(fig_nw, use_container_width=True)
else:
    st.info("📈 Your net worth trend builds as the app runs — check back after a couple of daily syncs.")

# ── This month vs last month ──────────────────────────────────────────────────
mom = get_month_over_month()
mom_cats = [c for c in mom.get("categories", []) if c["pct_change"] is not None]
if mom_cats:
    st.markdown("---")
    st.subheader("📊 This Month vs Last")
    st.caption(
        f"Compared to the same point last month (day {mom.get('day_of_month', '?')})."
    )

    total_this = mom.get("total_this_month", 0)
    total_prev = mom.get("total_last_month_same_point", 0)
    if total_prev > 0:
        total_pct = round((total_this - total_prev) / total_prev * 100, 1)
        st.markdown(f"**Total spending:** ${total_this:,.0f} (${total_pct:+.0f}% vs last month)")

    # Show all categories in a clean table with color-coded changes
    st.markdown("")
    df_mom = pd.DataFrame(mom_cats)
    df_mom = df_mom[["category", "this_month", "last_month_same_point", "pct_change"]]
    df_mom.columns = ["Category", "This Month", "Last Month", "% Change"]
    df_mom["This Month"] = df_mom["This Month"].apply(lambda x: f"${x:,.2f}")
    df_mom["Last Month"] = df_mom["Last Month"].apply(
        lambda x: f"${x:,.2f}" if x else "—"
    )
    df_mom["% Change"] = df_mom["% Change"].apply(
        lambda x: f"🔺 +{x:.0f}%" if x > 0 else (f"🔻 {x:.0f}%" if x < 0 else "▪️ 0%")
    )
    st.dataframe(df_mom, use_container_width=True, hide_index=True)

st.markdown("---")

# ── Account balance cards ─────────────────────────────────────────────────────
st.subheader("Account Balances")
cols = st.columns(min(len(accounts), 5))

for i, acct in enumerate(accounts):
    meta = INST_META.get(acct["institution"].split("_")[0], {"icon": "🏛️", "color": "#6b7280"})
    is_credit = acct["account_type"] in CREDIT_TYPES
    balance_label = f"-${acct['balance']:,.2f}" if is_credit else f"${acct['balance']:,.2f}"
    delta_color = "inverse" if is_credit else "normal"

    with cols[i % len(cols)]:
        st.metric(
            label=f"{meta['icon']} {acct['name']}",
            value=balance_label,
            delta=acct["institution"].title(),
            delta_color="off",
        )
        if acct.get("last_synced"):
            synced_dt = acct["last_synced"]
            if isinstance(synced_dt, str):
                synced_dt = datetime.fromisoformat(synced_dt.replace("Z", "+00:00"))
            st.caption(f"Synced {synced_dt.strftime('%b %d %I:%M %p')}")

st.markdown("---")

# ── Charts row ────────────────────────────────────────────────────────────────
chart_left, chart_right = st.columns([1, 1])

with chart_left:
    st.subheader("Spending by Category")
    if summary:
        df_summary = pd.DataFrame(summary).head(10)
        fig_pie = px.pie(
            df_summary,
            values="total",
            names="category",
            color_discrete_sequence=get_color_palette(),
            hole=0.4,
        )
        layout = get_plotly_layout()
        layout["legend"] = dict(font=dict(size=11))
        fig_pie.update_layout(**layout)
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No spending data yet.")

with chart_right:
    st.subheader("Daily Spending")
    if transactions:
        df_txn = pd.DataFrame(transactions)
        df_txn["date"] = pd.to_datetime(df_txn["date"], format="ISO8601").dt.date
        df_daily = (
            df_txn[df_txn["amount"] > 0]
            .groupby("date")["amount"]
            .sum()
            .reset_index()
            .rename(columns={"amount": "Spent"})
        )
        fig_bar = px.bar(
            df_daily,
            x="date",
            y="Spent",
            color_discrete_sequence=get_color_palette()[:1],
        )
        fig_bar.update_layout(**get_plotly_layout())
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No transaction data yet.")

# ── Recent transactions ───────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Recent Transactions")
recent = sorted(transactions, key=lambda t: t["date"], reverse=True)[:10]
if recent:
    df_recent = pd.DataFrame(recent)[["date", "description", "amount", "category", "account_id"]]
    df_recent["date"] = pd.to_datetime(df_recent["date"], format="ISO8601").dt.strftime("%b %d")
    df_recent["amount"] = df_recent["amount"].apply(lambda x: f"${x:,.2f}" if x > 0 else f"-${abs(x):,.2f}")
    df_recent.columns = ["Date", "Description", "Amount", "Category", "Account"]
    st.dataframe(df_recent, use_container_width=True, hide_index=True)
else:
    st.info("No transactions yet — sync your accounts to see data here.")
