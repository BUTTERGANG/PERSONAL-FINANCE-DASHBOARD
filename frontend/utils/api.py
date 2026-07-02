"""
HTTP client for Streamlit → FastAPI communication.
All calls are cached with TTL to avoid hammering the backend on every rerun.
"""

import os

import httpx
import streamlit as st

_BASE = os.getenv("BACKEND_URL", "http://localhost:8000")
_TIMEOUT = 10.0


def _get(path: str, params: dict | None = None):
    try:
        r = httpx.get(f"{_BASE}{path}", params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        st.error("Cannot reach the backend API. Make sure FastAPI is running on port 8000.")
        st.stop()
    except httpx.HTTPStatusError as exc:
        st.error(f"API error {exc.response.status_code}: {exc.response.text}")
        st.stop()


def _post(path: str, json: dict | None = None):
    try:
        r = httpx.post(f"{_BASE}{path}", json=json, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        st.error("Cannot reach the backend API.")
        st.stop()
    except httpx.HTTPStatusError as exc:
        st.error(f"API error {exc.response.status_code}: {exc.response.text}")
        st.stop()


@st.cache_data(ttl=300)
def get_accounts() -> list[dict]:
    return _get("/api/accounts/") or []


@st.cache_data(ttl=300)
def get_transactions(days: int = 30, account_id: str | None = None, search: str | None = None, category: str | None = None) -> list[dict]:
    params = {"days": days}
    if account_id:
        params["account_id"] = account_id
    if search:
        params["search"] = search
    if category:
        params["category"] = category
    return _get("/api/transactions/", params=params) or []


@st.cache_data(ttl=300)
def get_spending_summary(days: int = 30) -> list[dict]:
    return _get("/api/transactions/summary", params={"days": days}) or []


@st.cache_data(ttl=300)
def get_categories() -> list[str]:
    return _get("/api/transactions/categories") or []


@st.cache_data(ttl=60)
def get_sync_logs() -> list[dict]:
    return _get("/api/sync/logs") or []


@st.cache_data(ttl=300)
def get_networth_snapshots(days: int = 90) -> list[dict]:
    return _get("/api/networth/snapshots", params={"days": days}) or []


@st.cache_data(ttl=300)
def get_month_over_month() -> dict:
    return _get("/api/transactions/mom") or {}


@st.cache_data(ttl=60)
def get_budgets() -> list[dict]:
    return _get("/api/budgets/") or []


def set_budget(category: str, limit_amount: float) -> dict:
    result = _post("/api/budgets/", json={"category": category, "limit_amount": limit_amount}) or {}
    get_budgets.clear()
    return result


def delete_budget(category: str) -> None:
    try:
        httpx.delete(f"{_BASE}/api/budgets/{category}", timeout=_TIMEOUT)
    except httpx.HTTPError as exc:
        st.error(f"Failed to delete budget: {exc}")
    get_budgets.clear()


@st.cache_data(ttl=300)
def get_subscriptions() -> list[dict]:
    return _get("/api/subscriptions/") or []


def ignore_subscription(merchant_key: str) -> None:
    _post("/api/subscriptions/ignore", json={"merchant_key": merchant_key})
    get_subscriptions.clear()


def unignore_subscription(merchant_key: str) -> None:
    try:
        httpx.delete(f"{_BASE}/api/subscriptions/ignore/{merchant_key}", timeout=_TIMEOUT)
    except httpx.HTTPError as exc:
        st.error(f"Failed to restore subscription: {exc}")
    get_subscriptions.clear()


def create_manual_account(name: str, account_type: str, balance: float) -> dict:
    result = _post(
        "/api/manual/accounts",
        json={"name": name, "account_type": account_type, "balance": balance},
    ) or {}
    get_accounts.clear()
    get_networth_snapshots.clear()
    return result


def update_manual_balance(account_id: str, balance: float) -> None:
    try:
        r = httpx.patch(
            f"{_BASE}/api/manual/accounts/{account_id}",
            json={"balance": balance},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
    except httpx.HTTPError as exc:
        st.error(f"Failed to update balance: {exc}")
    get_accounts.clear()


def import_transactions(account_id: str, transactions: list[dict]) -> dict:
    result = _post(
        "/api/manual/import",
        json={"account_id": account_id, "transactions": transactions},
    ) or {}
    get_transactions.clear()
    get_spending_summary.clear()
    get_categories.clear()
    get_subscriptions.clear()
    get_budgets.clear()
    get_month_over_month.clear()
    return result


def trigger_sync() -> dict:
    """Background sync — returns immediately, balance uses cached data (free)."""
    get_accounts.clear()
    get_transactions.clear()
    get_spending_summary.clear()
    get_sync_logs.clear()
    get_networth_snapshots.clear()
    get_month_over_month.clear()
    return _post("/api/sync/trigger") or {}


def trigger_sync_realtime() -> dict:
    """
    Manual sync with live balance fetch ($0.10/account via Plaid Balance product).
    Runs synchronously — waits for completion and returns results.
    """
    try:
        r = httpx.post(
            f"{_BASE}/api/sync/trigger",
            params={"force_realtime": "true"},
            timeout=60.0,  # full sync can take ~20s across multiple accounts
        )
        r.raise_for_status()
        result = r.json()
    except httpx.ConnectError:
        st.error("Cannot reach the backend API.")
        st.stop()
    except httpx.HTTPStatusError as exc:
        st.error(f"API error {exc.response.status_code}: {exc.response.text}")
        st.stop()
    # Clear caches so the updated balances/transactions load on next page access
    get_accounts.clear()
    get_transactions.clear()
    get_spending_summary.clear()
    get_sync_logs.clear()
    get_networth_snapshots.clear()
    get_month_over_month.clear()
    return result or {}


def get_plaid_link_url() -> str:
    return f"{_BASE}/api/plaid/link"
