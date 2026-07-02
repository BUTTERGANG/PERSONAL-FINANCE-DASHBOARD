from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Transaction

router = APIRouter()

_UTC = timezone.utc


class TransactionOut(BaseModel):
    id: str
    account_id: str
    date: datetime
    amount: float
    description: str
    category: Optional[str]
    merchant: Optional[str]
    pending: bool
    source: str

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[TransactionOut])
def list_transactions(
    account_id: Optional[str] = None,
    days: int = Query(default=30, ge=1, le=365),
    search: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    since = datetime.now(_UTC) - timedelta(days=days)
    q = db.query(Transaction).filter(Transaction.date >= since)

    if account_id:
        q = q.filter(Transaction.account_id == account_id)
    if category:
        q = q.filter(Transaction.category == category)
    if search:
        q = q.filter(Transaction.description.ilike(f"%{search}%"))

    return q.order_by(Transaction.date.desc()).limit(500).all()


@router.get("/summary")
def spending_summary(days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)):
    since = datetime.now(_UTC) - timedelta(days=days)
    rows = (
        db.query(Transaction.category, func.sum(Transaction.amount).label("total"))
        .filter(Transaction.date >= since, Transaction.amount > 0, Transaction.pending == False)
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )
    return [{"category": r.category or "Uncategorized", "total": round(r.total, 2)} for r in rows]


@router.get("/mom")
def month_over_month(db: Session = Depends(get_db)):
    """
    Compare this calendar month's spending to last month's, by category.
    Last month's total is prorated to the same day-of-month so early-month
    comparisons aren't uselessly lopsided.
    """
    now = datetime.now(_UTC)
    this_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_start = (this_start - timedelta(days=1)).replace(day=1)

    def _spent(start: datetime, end: datetime) -> dict[str, float]:
        rows = (
            db.query(Transaction.category, func.sum(Transaction.amount).label("total"))
            .filter(
                Transaction.date >= start,
                Transaction.date < end,
                Transaction.amount > 0,
                Transaction.pending == False,
            )
            .group_by(Transaction.category)
            .all()
        )
        return {(r.category or "Uncategorized"): float(r.total or 0.0) for r in rows}

    this_month = _spent(this_start, now)
    last_full = _spent(last_start, this_start)
    # Same-day-of-month slice of last month, for a fair pace comparison.
    last_to_date = _spent(last_start, min(last_start + (now - this_start), this_start))

    out = []
    for category in sorted(set(this_month) | set(last_full)):
        cur = round(this_month.get(category, 0.0), 2)
        prev_full = round(last_full.get(category, 0.0), 2)
        prev_pace = round(last_to_date.get(category, 0.0), 2)
        base = prev_pace if prev_pace > 0 else None
        pct_change = round((cur - base) / base * 100, 1) if base else None
        out.append(
            {
                "category": category,
                "this_month": cur,
                "last_month_same_point": prev_pace,
                "last_month_total": prev_full,
                "pct_change": pct_change,  # None = no spend at this point last month
            }
        )

    out.sort(key=lambda r: r["this_month"], reverse=True)
    return {
        "month": this_start.strftime("%Y-%m"),
        "prev_month": last_start.strftime("%Y-%m"),
        "day_of_month": now.day,
        "categories": out,
        "total_this_month": round(sum(r["this_month"] for r in out), 2),
        "total_last_month_same_point": round(sum(r["last_month_same_point"] for r in out), 2),
    }


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    rows = (
        db.query(Transaction.category)
        .filter(Transaction.category.isnot(None))
        .distinct()
        .order_by(Transaction.category)
        .all()
    )
    return [r.category for r in rows]
