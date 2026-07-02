"""
Manual accounts + CSV transaction import — makes the dashboard usable
without Plaid (or backfills history Plaid can't provide).

Manual accounts are ordinary Account rows with an id prefixed "manual-" and
no Plaid token; they flow into net worth snapshots automatically. Imported
transactions get deterministic content-hash ids ("csv-...") so re-importing
the same file is idempotent.
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account, Transaction

router = APIRouter()

_UTC = timezone.utc

MANUAL_TYPES = {"checking", "savings", "credit", "investment", "loan", "asset", "cash"}


def _now() -> datetime:
    return datetime.now(_UTC)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "account"


# ── Manual accounts ───────────────────────────────────────────────────────────

class ManualAccountIn(BaseModel):
    name: str
    account_type: str  # checking, savings, credit, investment, loan, asset, cash
    balance: float = 0.0
    institution: str = "manual"


class BalanceUpdate(BaseModel):
    balance: float


@router.post("/accounts")
def create_manual_account(payload: ManualAccountIn, db: Session = Depends(get_db)):
    if payload.account_type not in MANUAL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"account_type must be one of: {', '.join(sorted(MANUAL_TYPES))}",
        )
    account_id = f"manual-{_slug(payload.name)}"
    if db.get(Account, account_id):
        raise HTTPException(status_code=409, detail=f"Account '{account_id}' already exists.")

    acct = Account(
        id=account_id,
        name=payload.name,
        institution=payload.institution or "manual",
        account_type=payload.account_type,
        balance=payload.balance,
        currency="USD",
        is_active=True,
        last_synced=_now(),
    )
    db.add(acct)
    db.commit()
    return {"id": account_id, "status": "created"}


@router.patch("/accounts/{account_id}")
def update_manual_balance(account_id: str, payload: BalanceUpdate, db: Session = Depends(get_db)):
    acct = db.get(Account, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found.")
    if not account_id.startswith("manual-"):
        raise HTTPException(status_code=400, detail="Only manual accounts can be updated here.")
    acct.balance = payload.balance
    acct.last_synced = _now()
    db.commit()
    return {"id": account_id, "balance": payload.balance, "status": "updated"}


# ── CSV transaction import ────────────────────────────────────────────────────

class ImportTransaction(BaseModel):
    date: str  # YYYY-MM-DD
    amount: float  # positive = spend (Plaid convention; frontend offers sign flip)
    description: str
    category: Optional[str] = None


class ImportRequest(BaseModel):
    account_id: str
    transactions: list[ImportTransaction]


@router.post("/import")
def import_transactions(payload: ImportRequest, db: Session = Depends(get_db)):
    acct = db.get(Account, payload.account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found. Create it first.")
    if not payload.transactions:
        raise HTTPException(status_code=400, detail="No transactions provided.")

    added = skipped = 0
    for t in payload.transactions:
        try:
            d = datetime.strptime(t.date, "%Y-%m-%d").replace(tzinfo=_UTC)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Bad date '{t.date}' — expected YYYY-MM-DD.")

        # Deterministic id: same row imported twice = same id = skipped.
        digest = hashlib.sha1(
            f"{payload.account_id}|{t.date}|{t.amount:.2f}|{t.description.strip().lower()}".encode()
        ).hexdigest()[:20]
        txn_id = f"csv-{digest}"

        if db.get(Transaction, txn_id):
            skipped += 1
            continue

        db.add(
            Transaction(
                id=txn_id,
                account_id=payload.account_id,
                date=d,
                amount=t.amount,
                description=t.description.strip(),
                category=(t.category or "").strip() or None,
                merchant=None,
                pending=False,
                source="csv",
            )
        )
        added += 1

    db.commit()
    return {"status": "imported", "added": added, "skipped_duplicates": skipped}
