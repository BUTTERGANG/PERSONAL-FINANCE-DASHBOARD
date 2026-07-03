"""
Manual accounts + CSV/PDF transaction import — makes the dashboard usable
without Plaid (or backfills history Plaid can't provide).

Manual accounts are ordinary Account rows with an id prefixed "manual-" and
no Plaid token; they flow into net worth snapshots automatically. Imported
transactions get deterministic content-hash ids ("csv-..." / "pdf-...") so
re-importing the same file is idempotent.
"""

import hashlib
import re
import tempfile
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account, Transaction
from ..pdf_parser import parse_pdf_statement

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

def get_api_key(request: Request):
    """Dependency to extract and validate API key from request headers."""
    api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization")
    if api_key and api_key.startswith("Bearer "):
        api_key = api_key[7:]
    return api_key

# ── Manual accounts ────────────────────────────────────────────────────────────

@router.post("/accounts")
def create_manual_account(
    payload: ManualAccountIn,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    # TODO: Add API key validation here
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
def update_manual_balance(
    account_id: str,
    payload: BalanceUpdate,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    # TODO: Add API key validation here
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
def import_transactions(
    payload: ImportRequest,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    # TODO: Add API key validation here
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


# ── PDF statement import ─────────────────────────────────────────────────────

class ParsedTransaction(BaseModel):
    date: str  # YYYY-MM-DD
    amount: float
    description: str
    category: Optional[str] = None


class PDFPreviewResponse(BaseModel):
    bank_detected: str
    transactions: List[ParsedTransaction]
    transaction_count: int


@router.post("/import-pdf/preview", response_model=PDFPreviewResponse)
async def preview_pdf_import(
    file: UploadFile = File(...),
    bank_hint: Optional[str] = Form(None),
):
    """
    Parse a bank statement PDF and return preview of transactions.
    Does NOT save to database - use /import-pdf/confirm to save.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF.")

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        transactions, bank = parse_pdf_statement(tmp_path, bank_hint)
    finally:
        import os
        os.unlink(tmp_path)

    parsed = [
        ParsedTransaction(
            date=t["date"],
            amount=t["amount"],
            description=t["description"],
            category=t.get("category"),
        )
        for t in transactions
    ]

    return PDFPreviewResponse(
        bank_detected=bank,
        transactions=parsed,
        transaction_count=len(parsed),
    )


class PDFImportConfirmRequest(BaseModel):
    account_id: str
    transactions: List[ParsedTransaction]


@router.post("/import-pdf/confirm")
def confirm_pdf_import(payload: PDFImportConfirmRequest, db: Session = Depends(get_db)):
    """
    Confirm and save PDF-parsed transactions to database.
    """
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
        txn_id = f"pdf-{digest}"

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
                source="pdf",
            )
        )
        added += 1

    db.commit()
    return {"status": "imported", "added": added, "skipped_duplicates": skipped}
