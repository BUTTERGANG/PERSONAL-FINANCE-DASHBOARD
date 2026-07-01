"""
Streamlit entry point — sets page config and shared CSS theme.
Navigation is handled by Streamlit's multipage file-based routing (pages/ folder).
"""

import streamlit as st

from utils.auth import require_pin

st.set_page_config(
    page_title="Finance Dashboard",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

require_pin()

# ── Global CSS — dark fintech aesthetic ───────────────────────────────────────
st.markdown(
    """
<style>
  /* Page background */
  .stApp { background-color: #0f0f14; }

  /* Sidebar */
  [data-testid="stSidebar"] { background-color: #13131a; border-right: 1px solid #1e1e2e; }

  /* Hide default Streamlit header decoration */
  [data-testid="stDecoration"] { display: none; }

  /* Metric cards */
  [data-testid="metric-container"] {
    background: #1a1a24;
    border: 1px solid #2d2d3d;
    border-radius: 12px;
    padding: 16px 20px;
  }

  /* Dataframe */
  [data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

  /* Buttons */
  .stButton > button {
    background: #7c3aed;
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 500;
  }
  .stButton > button:hover { background: #6d28d9; border: none; }

  /* Success / error banners */
  .stAlert { border-radius: 10px; }

  /* Hide "Made with Streamlit" footer */
  footer { visibility: hidden; }
  #MainMenu { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)

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
