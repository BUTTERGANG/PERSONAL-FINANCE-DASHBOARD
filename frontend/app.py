"""
Streamlit entry point — sets page config and shared CSS theme.
Navigation is handled by Streamlit's multipage file-based routing (pages/ folder).
"""

import streamlit as st

from utils.auth import require_pin
from utils.themes import inject_theme_css, theme_toggle

st.set_page_config(
    page_title="Finance Dashboard",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

require_pin()
inject_theme_css()
theme_toggle()

# ── Home page ─────────────────────────────────────────────────────────────────
st.title("💰 Personal Finance Dashboard")
st.markdown(
    """
Welcome to your unified finance dashboard. Use the **sidebar** to navigate.

| Page | What it shows |
|------|--------------|
| 📊 Overview | Net worth, account balances, spending snapshot |
| 💳 Transactions | Full transaction history with filters |
| 🏦 Accounts | Linked accounts and sync status |
| 🔗 Link Account | Connect a new bank or Fidelity via OFX |
| ⚙️ Settings | Sync configuration and data export |

> Accounts sync automatically every 4 hours. Use **Sync Now** on any page to refresh immediately.
"""
)