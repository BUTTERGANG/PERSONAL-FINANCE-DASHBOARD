from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Budget, Transaction

router = APIRouter()

_UTC = timezone.utc


class BudgetIn(BaseModel):
    category: str
    limit_amount: float


class BudgetOut(BaseModel):
    category: str
    limit_amount: float
    spent: float
    remaining: float
    pct: float  # 0-100+, how much of the limit is used this month


def _month_start() -> datetime:
    now = datetime.now(_UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _spent_by_category(db: Session) -> dict[str, float]:
    """Total spend per category for the current calendar month."""
    rows = (
        db.query(Transaction.category, func.sum(Transaction.amount).label("total"))
        .filter(
            Transaction.date >= _month_start(),
            Transaction.amount > 0,
            Transaction.pending == False,
        )
        .group_by(Transaction.category)
        .all()
    )
    return {(r.category or "Uncategorized"): float(r.total or 0.0) for r in rows}


@router.get("/", response_model=list[BudgetOut])
def list_budgets(db: Session = Depends(get_db)):
    spent_map = _spent_by_category(db)
    budgets = db.query(Budget).order_by(Budget.category).all()

    out: list[BudgetOut] = []
    for b in budgets:
        spent = round(spent_map.get(b.category, 0.0), 2)
        remaining = round(b.limit_amount - spent, 2)
        pct = round((spent / b.limit_amount * 100) if b.limit_amount > 0 else 0.0, 1)
        out.append(
            BudgetOut(
                category=b.category,
                limit_amount=b.limit_amount,
                spent=spent,
                remaining=remaining,
                pct=pct,
            )
        )
    return out


@router.post("/", response_model=BudgetOut)
def upsert_budget(payload: BudgetIn, db: Session = Depends(get_db)):
    if payload.limit_amount <= 0:
        raise HTTPException(status_code=400, detail="limit_amount must be positive")

    budget = db.query(Budget).filter(Budget.category == payload.category).first()
    if budget:
        budget.limit_amount = payload.limit_amount
    else:
        budget = Budget(category=payload.category, limit_amount=payload.limit_amount)
        db.add(budget)
    db.commit()

    spent = round(_spent_by_category(db).get(payload.category, 0.0), 2)
    remaining = round(payload.limit_amount - spent, 2)
    pct = round((spent / payload.limit_amount * 100) if payload.limit_amount > 0 else 0.0, 1)
    return BudgetOut(
        category=payload.category,
        limit_amount=payload.limit_amount,
        spent=spent,
        remaining=remaining,
        pct=pct,
    )


@router.delete("/{category}")
def delete_budget(category: str, db: Session = Depends(get_db)):
    budget = db.query(Budget).filter(Budget.category == category).first()
    if budget:
        db.delete(budget)
        db.commit()
    return {"status": "deleted"}
