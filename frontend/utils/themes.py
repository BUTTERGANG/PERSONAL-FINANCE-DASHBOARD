"""
Theme configuration for dark/light mode support.
Centralized color definitions and CSS injection for consistent styling.
"""

import json
from typing import Any

import streamlit as st

# Theme definitions
THEMES: dict[str, dict[str, Any]] = {
    "dark": {
        "name": "Dark",
        "icon": "🌙",
        "colors": {
            "background": "#0f0f14",
            "sidebar": "#13131a",
            "border": "#2d2d3d",
            "primary": "#7c3aed",
            "primary_hover": "#6d28d9",
            "card": "#1a1a24",
            "text": "#f1f5f9",
            "grid": "#2d2d3d",
            "success": "#22c55e",
            "warning": "#f59e0b",
            "danger": "#f87171",
        },
    },
    "light": {
        "name": "Light",
        "icon": "☀️",
        "colors": {
            "background": "#fafafa",
            "sidebar": "#ffffff",
            "border": "#e5e7eb",
            "primary": "#7c3aed",
            "primary_hover": "#6d28d9",
            "card": "#ffffff",
            "text": "#111827",
            "grid": "#e5e7eb",
            "success": "#10b981",
            "warning": "#f59e0b",
            "danger": "#ef4444",
        },
    },
}


def get_theme() -> str:
    """Get the current theme from session state, defaulting to dark."""
    return st.session_state.get("theme", "dark")


def set_theme(theme: str) -> None:
    """Set the theme in session state and rerun."""
    st.session_state["theme"] = theme
    st.rerun()


def inject_theme_css() -> None:
    """Inject theme CSS into the page."""
    theme = get_theme()
    colors = THEMES[theme]["colors"]

    st.markdown(
        f"""
        <style>
          .stApp {{ background-color: {colors['background']}; }}
          [data-testid="stSidebar"] {{ background-color: {colors['sidebar']}; border-right: 1px solid {colors['border']}; }}
          [data-testid="stDecoration"] {{ display: none; }}

          [data-testid="metric-container"] {{
            background: {colors['card']};
            border: 1px solid {colors['border']};
            border-radius: 12px;
            padding: 16px 20px;
          }}

          .stButton > button {{
            background: {colors['primary']};
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 500;
          }}
          .stButton > button:hover {{ background: {colors['primary_hover']}; border: none; }}

          .stAlert {{ border-radius: 10px; }}

          footer {{ visibility: hidden; }}
          #MainMenu {{ visibility: hidden; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def theme_toggle() -> None:
    """Render a theme toggle in the sidebar."""
    current = get_theme()
    other_theme = "light" if current == "dark" else "dark"
    other = THEMES[other_theme]

    with st.sidebar:
        st.markdown("---")
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button(f"{other['icon']} {other_theme.title()}", key="theme_toggle"):
                set_theme(other_theme)


def get_plotly_layout(theme: str | None = None) -> dict:
    """Get theme-aware layout for Plotly charts."""
    theme = theme or get_theme()
    colors = THEMES[theme]["colors"]

    return {
        "paper_bgcolor": colors["card"],
        "plot_bgcolor": colors["card"],
        "font_color": colors["text"],
        "margin": dict(t=10, b=10, l=10, r=10),
        "xaxis": dict(showgrid=False),
        "yaxis": dict(showgrid=True, gridcolor=colors["grid"]),
    }


def get_color_palette(theme: str | None = None) -> list:
    """Get theme-aware color palette for charts."""
    theme = theme or get_theme()
    # Use a consistent palette that works for both themes
    return [
        "#7c3aed",  # purple
        "#22c55e",  # green
        "#f87171",  # red
        "#f59e0b",  # amber
        "#3b82f6",  # blue
        "#a855f7",  # violet
        "#ec4899",  # pink
        "#06b6d4",  # cyan
    ]