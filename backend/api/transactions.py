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
