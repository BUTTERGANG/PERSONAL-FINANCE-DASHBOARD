"""
Sync orchestrator — pulls from Plaid and Fidelity OFX, writes to SQLite.
Called both by APScheduler (auto) and by the manual trigger endpoint.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from . import fidelity_client
from .crypto import decrypt
from .models import CREDIT_TYPES, Account, NetWorthSnapshot, SyncLog, Transaction
from .plaid_client import fetch_balances_realtime, fetch_transactions

logger = logging.getLogger(__name__)

_UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(_UTC)


# ── Plaid accounts ────────────────────────────────────────────────────────────

def sync_plaid_account(db: Session, account: Account, force_realtime: bool = False) -> int:
    """
    Sync one Plaid-linked account: update balance + upsert new transactions.
    force_realtime=True fetches live balance via /accounts/balance/get ($0.10/call).
    Returns the number of transactions added.
    """
    added = 0
    try:
        access_token = decrypt(account.plaid_access_token_enc)

        if force_realtime:
            # Live balance pull — costs $0.10, used only on manual "Sync Now"
            try:
                live = fetch_balances_realtime(access_token)
                for acct_data in live:
                    if acct_data["account_id"] == account.id:
                        account.balance = acct_data["balances"]["current"] or 0.0
                        account.available_balance = acct_data["balances"].get("available")
            except Exception as exc:
                logger.warning("Real-time balance fetch failed, falling back to cached: %s", exc)

        result = fetch_transactions(access_token)
        while True:
            if not force_realtime:
                # Update balance from cached sync response (free)
                for acct_data in result.get("accounts", []):
                    if acct_data["account_id"] == account.id:
                        account.balance = acct_data["balances"]["current"] or 0.0
                        account.available_balance = acct_data["balances"].get("available")
            for txn in result["added"]:
                if not db.get(Transaction, txn["transaction_id"]):
                    category = None
                    if txn.get("personal_finance_category"):
                        category = txn["personal_finance_category"].get("primary")

                    db.add(
                        Transaction(
                            id=txn["transaction_id"],
                            account_id=account.id,
                            date=_parse_date(txn["date"]),
                            amount=txn["amount"],
                            description=txn.get("name") or txn.get("merchant_name") or "",
                            category=category,
                            merchant=txn.get("merchant_name"),
                            pending=txn.get("pending", False),
                            source="plaid",
                            created_at=_now(),
                        )
                    )
                    added += 1

            # Handle modified transactions
            for txn in result["modified"]:
                existing = db.get(Transaction, txn["transaction_id"])
                if existing:
                    existing.amount = txn["amount"]
                    existing.pending = txn.get("pending", False)
                    existing.description = txn.get("name") or existing.description

            # Handle removed transactions
            for removed in result["removed"]:
                existing = db.get(Transaction, removed["transaction_id"])
                if existing:
                    db.delete(existing)

            if not result["has_more"]:
                break
            result = fetch_transactions(access_token, cursor=result["next_cursor"])

        account.last_synced = _now()
        db.commit()

        db.add(
            SyncLog(
                account_id=account.id,
                institution=account.institution,
                status="success",
                transactions_added=added,
                synced_at=_now(),
            )
        )
        db.commit()
        return added

    except Exception as exc:
        db.rollback()
        logger.error("Plaid sync failed for account %s: %s", account.id, exc)
        db.add(
            SyncLog(
                account_id=account.id,
                institution=account.institution,
                status="error",
                error_message=str(exc),
                synced_at=_now(),
            )
        )
        db.commit()
        raise


# ── Fidelity OFX ─────────────────────────────────────────────────────────────

def sync_fidelity(db: Session) -> int:
    """
    Sync Fidelity account via OFX direct connect.
    Returns the number of transactions added.
    """
    if not fidelity_client.is_configured():
        return 0

    added = 0
    try:
        fidelity_acct = db.query(Account).filter(Account.institution == "fidelity").first()
        if not fidelity_acct:
            logger.info("No Fidelity account record found — skipping OFX sync.")
            return 0

        transactions = fidelity_client.fetch_transactions(days_back=30)
        for txn in transactions:
            if not db.get(Transaction, txn["id"]):
                db.add(
                    Transaction(
                        id=txn["id"],
                        account_id=fidelity_acct.id,
                        date=txn["date"],
                        amount=txn["amount"],
                        description=txn["description"],
                        category="Investment",
                        source="ofx",
                        created_at=_now(),
                    )
                )
                added += 1

        # Update balance
        balance = fidelity_client.fetch_balance()
        if balance is not None:
            fidelity_acct.balance = balance

        fidelity_acct.last_synced = _now()
        db.commit()

        db.add(
            SyncLog(
                institution="fidelity",
                status="success",
                transactions_added=added,
                synced_at=_now(),
            )
        )
        db.commit()
        return added

    except Exception as exc:
        db.rollback()
        logger.error("Fidelity OFX sync failed: %s", exc)
        db.add(
            SyncLog(
                institution="fidelity",
                status="error",
                error_message=str(exc),
                synced_at=_now(),
            )
        )
        db.commit()
        raise


# ── Net worth snapshots ───────────────────────────────────────────────────────

def record_net_worth_snapshot(db: Session) -> NetWorthSnapshot:
    """
    Capture today's net worth as a single row (upsert one per UTC calendar day).
    Called at the end of sync_all so the trend chart accrues history automatically.
    Assets minus debts, where debts = accounts whose type is in CREDIT_TYPES.
    """
    accounts = db.query(Account).filter(Account.is_active == True).all()

    assets = sum(a.balance or 0.0 for a in accounts if a.account_type not in CREDIT_TYPES)
    debts = sum(a.balance or 0.0 for a in accounts if a.account_type in CREDIT_TYPES)
    net_worth = assets - debts

    breakdown = {a.institution: round(a.balance or 0.0, 2) for a in accounts}
    day = _now().strftime("%Y-%m-%d")

    snapshot = db.query(NetWorthSnapshot).filter(NetWorthSnapshot.day == day).first()
    if snapshot:
        snapshot.captured_at = _now()
        snapshot.net_worth = round(net_worth, 2)
        snapshot.total_assets = round(assets, 2)
        snapshot.total_debt = round(debts, 2)
        snapshot.breakdown_json = json.dumps(breakdown)
    else:
        snapshot = NetWorthSnapshot(
            day=day,
            captured_at=_now(),
            net_worth=round(net_worth, 2),
            total_assets=round(assets, 2),
            total_debt=round(debts, 2),
            breakdown_json=json.dumps(breakdown),
        )
        db.add(snapshot)

    db.commit()
    return snapshot


# ── Full sync ─────────────────────────────────────────────────────────────────

def sync_all(db: Session, force_realtime: bool = False) -> dict:
    """
    Run a full sync of all accounts. Called by scheduler and manual trigger.
    force_realtime=True fetches live balances ($0.10/account) — use for manual triggers only.
    Returns a summary dict.
    """
    results = {"plaid": {}, "fidelity": 0, "errors": [], "realtime": force_realtime}

    plaid_accounts = (
        db.query(Account)
        .filter(Account.is_active == True, Account.plaid_access_token_enc.isnot(None))
        .all()
    )

    for acct in plaid_accounts:
        try:
            count = sync_plaid_account(db, acct, force_realtime=force_realtime)
            results["plaid"][acct.institution] = count
        except Exception as exc:
            results["errors"].append(f"{acct.institution}: {exc}")

    try:
        results["fidelity"] = sync_fidelity(db)
    except Exception as exc:
        results["errors"].append(f"fidelity: {exc}")

    # Capture net worth for the trend chart. Never let a snapshot failure break a sync.
    try:
        snap = record_net_worth_snapshot(db)
        results["net_worth"] = snap.net_worth
    except Exception as exc:
        logger.error("Net worth snapshot failed: %s", exc)
        results["errors"].append(f"snapshot: {exc}")

    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_date(date_val) -> datetime:
    if isinstance(date_val, datetime):
        return date_val if date_val.tzinfo else date_val.replace(tzinfo=_UTC)
    if isinstance(date_val, str):
        from datetime import date
        d = date.fromisoformat(date_val)
        return datetime(d.year, d.month, d.day, tzinfo=_UTC)
    return _now()
