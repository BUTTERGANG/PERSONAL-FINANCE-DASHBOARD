"""
Import page — manual accounts (401k, car, cash...) and CSV transaction import.
Works entirely without Plaid: create an account, upload a bank-statement CSV,
map the columns, import. Re-importing the same file skips duplicates.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st

from utils.api import (
    create_manual_account,
    get_accounts,
    import_transactions,
    update_manual_balance,
)
from utils.auth import require_pin
from utils.themes import get_color_palette, get_plotly_layout

st.set_page_config(page_title="Import", page_icon="📥", layout="wide")
require_pin()

st.title("📥 Import")
st.caption("Track accounts and import bank-statement CSVs — no bank connection required.")

tab_csv, tab_manual = st.tabs(["📄 CSV Transactions", "🏛️ Manual Accounts"])

# ── Manual accounts ───────────────────────────────────────────────────────────
with tab_manual:
    st.subheader("Add a manual account")
    st.caption("For anything you track by hand: 401k, car value, mortgage, cash. Debts (credit/loan) subtract from net worth.")

    with st.form("add_manual", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        with c1:
            name = st.text_input("Account name", placeholder="e.g. Fidelity 401k")
        with c2:
            acct_type = st.selectbox("Type", ["checking", "savings", "credit", "investment", "loan", "asset", "cash"])
        with c3:
            balance = st.number_input("Balance ($)", step=100.0, value=0.0)
        with c4:
            st.write("")
            st.write("")
            submitted = st.form_submit_button("➕ Add")
        if submitted and name:
            result = create_manual_account(name, acct_type, float(balance))
            if result.get("status") == "created":
                st.success(f"Added {name} (${balance:,.2f})")
                st.rerun()

    st.markdown("---")
    st.subheader("Update balances")
    manual_accounts = [a for a in get_accounts() if a["id"].startswith("manual-")]
    if not manual_accounts:
        st.info("No manual accounts yet.")
    for acct in manual_accounts:
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            st.markdown(f"**{acct['name']}** · {acct['account_type'].title()}")
        with c2:
            new_bal = st.number_input(
                "Balance", value=float(acct["balance"]), step=100.0,
                key=f"bal_{acct['id']}", label_visibility="collapsed",
            )
        with c3:
            if st.button("💾 Update", key=f"upd_{acct['id']}"):
                update_manual_balance(acct["id"], float(new_bal))
                st.success(f"{acct['name']} → ${new_bal:,.2f}")
                st.rerun()

# ── CSV import ────────────────────────────────────────────────────────────────
with tab_csv:
    accounts = get_accounts()
    if not accounts:
        st.info("Create an account first (Manual Accounts tab) so transactions have somewhere to go.")
        st.stop()

    st.subheader("1 · Choose the destination account")
    acct_options = {f"{a['name']} ({a['institution']})": a["id"] for a in accounts}
    acct_label = st.selectbox("Account", list(acct_options.keys()))
    account_id = acct_options[acct_label]

    st.subheader("2 · Upload the CSV")
    uploaded = st.file_uploader("Bank statement CSV", type=["csv"])
    if not uploaded:
        st.caption("Export a statement from your bank's website as CSV, then drop it here.")
        st.stop()

    try:
        df = pd.read_csv(uploaded)
    except Exception as exc:
        st.error(f"Could not parse CSV: {exc}")
        st.stop()
    if df.empty:
        st.warning("CSV has no rows.")
        st.stop()

    st.dataframe(df.head(5), use_container_width=True, hide_index=True)
    st.caption(f"{len(df)} rows detected. Map the columns below.")

    st.subheader("3 · Map columns")
    cols = list(df.columns)

    def _guess(candidates: list[str]) -> int:
        for i, c in enumerate(cols):
            if any(k in c.lower() for k in candidates):
                return i
        return 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        date_col = st.selectbox("Date column", cols, index=_guess(["date", "posted"]))
    with c2:
        amount_col = st.selectbox("Amount column", cols, index=_guess(["amount", "amt", "debit"]))
    with c3:
        desc_col = st.selectbox("Description column", cols, index=_guess(["desc", "name", "payee", "memo"]))
    with c4:
        cat_options = ["(none)"] + cols
        cat_col = st.selectbox("Category column (optional)", cat_options, index=0)

    flip_sign = st.checkbox(
        "Flip amount signs",
        help="This app stores spending as POSITIVE amounts (Plaid convention). "
             "If your bank exports spending as negative numbers, check this box.",
    )

    st.subheader("4 · Import")
    if st.button("📥 Import transactions"):
        rows, errors = [], 0
        for _, r in df.iterrows():
            try:
                d = pd.to_datetime(r[date_col]).strftime("%Y-%m-%d")
                amt = float(r[amount_col])
                if flip_sign:
                    amt = -amt
                desc = str(r[desc_col]).strip()
                if not desc or pd.isna(r[amount_col]):
                    errors += 1
                    continue
                row = {"date": d, "amount": amt, "description": desc}
                if cat_col != "(none)" and pd.notna(r[cat_col]):
                    row["category"] = str(r[cat_col]).strip()
                rows.append(row)
            except Exception:
                errors += 1

        if not rows:
            st.error("No valid rows found — check the column mapping.")
            st.stop()

        with st.spinner(f"Importing {len(rows)} transactions..."):
            result = import_transactions(account_id, rows)
        added = result.get("added", 0)
        skipped = result.get("skipped_duplicates", 0)
        msg = f"✅ Imported {added} transactions"
        if skipped:
            msg += f" · {skipped} duplicates skipped"
        if errors:
            msg += f" · {errors} unparseable rows ignored"
        st.success(msg)
        st.balloons()
