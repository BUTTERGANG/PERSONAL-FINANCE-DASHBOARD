"""
Plaid API client — handles Link token creation, public token exchange,
account fetching, and transaction sync for Chase, Citi, PayPal, and Venmo.

Cost notes:
- /accounts/get        → FREE with Transactions product (cached balance)
- /accounts/balance/get → $0.10 per call (real-time balance) — NOT used here
- /transactions/sync   → covered by $0.30/account/month Transactions fee
"""

import plaid
from plaid.api import plaid_api
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest

from .config import get_settings

# Plaid sunset the "development" environment — the modern SDK exposes only
# Sandbox and Production. "development" is mapped to Production for back-compat.
_ENV_MAP = {
    "sandbox": plaid.Environment.Sandbox,
    "development": plaid.Environment.Production,
    "production": plaid.Environment.Production,
}


def _get_client() -> plaid_api.PlaidApi:
    settings = get_settings()
    host = _ENV_MAP.get(settings.plaid_env)
    if host is None:
        raise ValueError(
            f"Invalid PLAID_ENV '{settings.plaid_env}'. Use 'sandbox' or 'production'."
        )
    configuration = plaid.Configuration(
        host=host,
        api_key={
            "clientId": settings.plaid_client_id,
            "secret": settings.plaid_secret,
        },
    )
    return plaid_api.PlaidApi(plaid.ApiClient(configuration))


def create_link_token(user_id: str = "local-user") -> str:
    request = LinkTokenCreateRequest(
        products=[Products("transactions"), Products("balance")],
        client_name="Personal Finance Dashboard",
        country_codes=[CountryCode("US")],
        language="en",
        user=LinkTokenCreateRequestUser(client_user_id=user_id),
    )
    response = _get_client().link_token_create(request)
    return response["link_token"]


def exchange_public_token(public_token: str) -> dict:
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = _get_client().item_public_token_exchange(request)
    return {
        "access_token": response["access_token"],
        "item_id": response["item_id"],
    }


def fetch_accounts(access_token: str) -> list:
    """
    Fetch account info and cached balances via /accounts/get.
    FREE with the Transactions product — use this everywhere instead of
    accounts_balance_get which costs $0.10 per call.
    """
    request = AccountsGetRequest(access_token=access_token)
    response = _get_client().accounts_get(request)
    return response["accounts"]


def fetch_balances_realtime(access_token: str) -> list:
    """
    Real-time balance via /accounts/balance/get — $0.10 per call.
    Use ONLY for user-triggered manual syncs, never in the auto-scheduler.
    Requires the Balance product to have been requested at Link time.
    """
    request = AccountsBalanceGetRequest(access_token=access_token)
    response = _get_client().accounts_balance_get(request)
    return response["accounts"]


def fetch_transactions(access_token: str, cursor: str = "") -> dict:
    """
    Uses Plaid's /transactions/sync endpoint — incremental, cursor-based.
    Returns added, modified, removed transactions, the next cursor, AND
    accounts with their latest cached balances (no extra API call needed).
    """
    request = TransactionsSyncRequest(access_token=access_token, cursor=cursor)
    response = _get_client().transactions_sync(request)
    return {
        "added": response["added"],
        "modified": response["modified"],
        "removed": response["removed"],
        "next_cursor": response["next_cursor"],
        "has_more": response["has_more"],
        "accounts": response.get("accounts", []),
    }
