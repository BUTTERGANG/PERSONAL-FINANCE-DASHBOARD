"""
Manual accounts + CSV/PDF transaction import — makes the dashboard usable
without Plaid (or backfills history Plaid can't provide).

Manual accounts are ordinary Account rows with an id prefixed "manual-" and
no Plaid token; they flow into net worth snapshots automatically. Imported
transactions get deterministic content-hash ids ("csv-..." / "pdf-...") so
re-importing the same file is idempotent.
"""

import hashlib
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account, CategoryRule, Transaction
from ..pdf_parser import parse_statement
from ..categorize import auto_categorize


def _load_rules(db: Session) -> dict:
    """Learned merchant→category rules, for auto-categorizing imported rows."""
    return {r.merchant_key: r.category for r in db.query(CategoryRule).all()}


def _resolve_category(explicit: Optional[str], description: str, amount: float,
                      rules: dict) -> Optional[str]:
    """Use an explicit category if present, else auto-categorize the row."""
    explicit = (explicit or "").strip() or None
    if explicit:
        return explicit
    return auto_categorize(description, amount, None, rules)

router = APIRouter()

_UTC = timezone.utc

MANUAL_TYPES = {"checking", "savings", "credit", "investment", "loan", "asset", "cash"}

# Import id prefixes — a transaction is the "same row" regardless of which format
# it arrived in, so dedup checks every prefix (a CSV export and the PDF statement
# of the same month must not both persist the same transaction).
_IMPORT_PREFIXES = ("csv-", "pdf-")


def _txn_digest(account_id: str, date: str, amount: float, description: str) -> str:
    """Content hash identifying a transaction independent of import source."""
    return hashlib.sha1(
        f"{account_id}|{date}|{amount:.2f}|{description.strip().lower()}".encode()
    ).hexdigest()[:20]


def _existing_txn_id(db: Session, digest: str) -> Optional[str]:
    """Return an existing transaction id for this digest under any import prefix."""
    for prefix in _IMPORT_PREFIXES:
        if db.get(Transaction, f"{prefix}{digest}"):
            return f"{prefix}{digest}"
    return None


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


# ── Manual accounts ────────────────────────────────────────────────────────────

@router.post("/accounts")
def create_manual_account(
    payload: ManualAccountIn,
    db: Session = Depends(get_db),
):
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
    db: Session = Depends(get_db),
):
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
    db: Session = Depends(get_db),
):
    acct = db.get(Account, payload.account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found. Create it first.")
    if not payload.transactions:
        raise HTTPException(status_code=400, detail="No transactions provided.")

    rules = _load_rules(db)
    added = skipped = 0
    for t in payload.transactions:
        try:
            d = datetime.strptime(t.date, "%Y-%m-%d").replace(tzinfo=_UTC)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Bad date '{t.date}' — expected YYYY-MM-DD.")

        # Deterministic id: same row imported twice (any format) = skipped.
        digest = _txn_digest(payload.account_id, t.date, t.amount, t.description)
        if _existing_txn_id(db, digest):
            skipped += 1
            continue

        db.add(
            Transaction(
                id=f"csv-{digest}",
                account_id=payload.account_id,
                date=d,
                amount=t.amount,
                description=t.description.strip(),
                category=_resolve_category(t.category, t.description, t.amount, rules),
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


class HoldingOut(BaseModel):
    description: str
    symbol: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    market_value: Optional[float] = None
    cost_basis: Optional[float] = None
    unrealized_gain: Optional[float] = None


class PDFPreviewResponse(BaseModel):
    bank_detected: str
    statement_type: str            # e.g. "chase_checking", or bank name if unknown product
    parse_method: str              # "sectioned" | "legacy" | "generic_table" | "investment"
    transactions: List[ParsedTransaction]
    transaction_count: int
    # Investment holdings (Fidelity). Empty for transaction statements.
    holdings: List[HoldingOut] = []
    # Reconciliation: null when the statement type has no section config.
    # reconciled=True means parsed sums matched the statement's printed totals
    # to the penny — a strong signal the import is trustworthy.
    reconciled: Optional[bool] = None
    reconciliation: Optional[dict] = None
    # Headline figures from the statement summary (balances, due date, limits).
    # Keys vary by statement type, e.g. new_balance / minimum_payment_due /
    # credit_limit (credit card) or beginning_balance / ending_balance (checking).
    summary: dict = {}
    # The statement's stated account balance (Citi new balance, Chase ending
    # balance). Offer to sync this onto the account's balance on import.
    account_balance: Optional[float] = None


@router.post("/import-pdf/preview", response_model=PDFPreviewResponse)
async def preview_pdf_import(
    file: UploadFile = File(...),
    bank_hint: Optional[str] = Form(None),
):
    """
    Parse a bank statement PDF and return preview of transactions.
    Does NOT save to database - use /import-pdf/confirm to save.

    The response includes a reconciliation report: for statement types with a
    section config, parsed section sums are checked against the statement's own
    printed totals. reconciled=True → the numbers add up; reconciled=False →
    show a "review needed" warning before importing.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF.")

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = parse_statement(tmp_path, bank_hint)
    except Exception:
        # Corrupt, encrypted, or image-only PDF — surface a clear 422 rather than
        # a bare 500 stack trace.
        raise HTTPException(
            status_code=422,
            detail="Could not read this PDF. It may be encrypted, scanned (image-only), "
                   "or corrupt. Try a different export, or use the CSV tab.",
        )
    finally:
        os.unlink(tmp_path)

    parsed = [
        ParsedTransaction(
            date=t["date"],
            amount=t["amount"],
            description=t["description"],
            category=t.get("category"),
        )
        for t in result.transactions
    ]

    recon = result.reconciliation
    return PDFPreviewResponse(
        bank_detected=result.bank,
        statement_type=result.statement_type,
        parse_method=result.method,
        transactions=parsed,
        transaction_count=len(parsed),
        reconciled=(recon.ok if recon else None),
        reconciliation=(recon.as_dict() if recon else None),
        summary=result.summary,
        account_balance=result.account_balance,
        holdings=[HoldingOut(**h.as_dict()) for h in result.holdings],
    )


class PDFImportConfirmRequest(BaseModel):
    account_id: str
    transactions: List[ParsedTransaction] = []
    # When provided, the account's balance is set to this value (the statement's
    # ending/new balance). Lets a user sync the account to the statement, and lets
    # holdings-only statements (Fidelity investment/crypto) import with no rows.
    set_balance: Optional[float] = None


@router.post("/import-pdf/confirm")
def confirm_pdf_import(payload: PDFImportConfirmRequest, db: Session = Depends(get_db)):
    """
    Save PDF-parsed transactions and/or sync the account balance.

    Accepts three shapes:
      • transactions only  → import rows (checking / credit cards)
      • set_balance only   → sync the account value (Fidelity holdings statements)
      • both               → import rows and sync the balance
    """
    acct = db.get(Account, payload.account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found. Create it first.")
    if not payload.transactions and payload.set_balance is None:
        raise HTTPException(
            status_code=400,
            detail="Nothing to import — no transactions and no balance to sync.",
        )

    rules = _load_rules(db)
    added = skipped = 0
    for t in payload.transactions:
        try:
            d = datetime.strptime(t.date, "%Y-%m-%d").replace(tzinfo=_UTC)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Bad date '{t.date}' — expected YYYY-MM-DD.")

        # Deterministic id: same row imported twice (any format) = skipped.
        digest = _txn_digest(payload.account_id, t.date, t.amount, t.description)
        if _existing_txn_id(db, digest):
            skipped += 1
            continue

        db.add(
            Transaction(
                id=f"pdf-{digest}",
                account_id=payload.account_id,
                date=d,
                amount=t.amount,
                description=t.description.strip(),
                category=_resolve_category(t.category, t.description, t.amount, rules),
                merchant=None,
                pending=False,
                source="pdf",
            )
        )
        added += 1

    balance_updated = False
    if payload.set_balance is not None:
        acct.balance = payload.set_balance
        acct.last_synced = _now()
        balance_updated = True

    db.commit()
    return {
        "status": "imported",
        "added": added,
        "skipped_duplicates": skipped,
        "balance_updated": balance_updated,
    }
