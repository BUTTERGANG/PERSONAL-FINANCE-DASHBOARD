"""
PIN gate for the Streamlit dashboard.

Streamlit runs each page script independently, so `require_pin()` must be called
at the top of every page (and app.py) — st.session_state persists across pages
within a browser session, so once unlocked the user stays unlocked until the
session ends.

Security note: this is a frontend-only gate, which is the right size for this
deployment because only the Streamlit port (8501) is publicly mapped on Replit —
the FastAPI backend (8000) is internal. If you ever expose the backend publicly,
add real API auth (e.g. a token dependency) instead of relying on this.
"""

import hmac
import os

import streamlit as st

_PIN = os.getenv("DASHBOARD_PIN", "")


def require_pin() -> None:
    """Block the page with a PIN prompt unless the session is authenticated.

    No-op when DASHBOARD_PIN is unset, so the dashboard stays open by default.
    """
    if not _PIN:
        return

    if st.session_state.get("authenticated"):
        return

    # Dark background so the lock screen matches the app theme.
    st.markdown(
        "<style>.stApp { background-color: #0f0f14; }</style>",
        unsafe_allow_html=True,
    )
    st.title("🔒 Locked")
    st.caption("Enter your PIN to access the dashboard.")

    pin = st.text_input("PIN", type="password", label_visibility="collapsed", placeholder="PIN")
    if st.button("Unlock"):
        if hmac.compare_digest(pin, _PIN):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect PIN.")

    st.stop()
