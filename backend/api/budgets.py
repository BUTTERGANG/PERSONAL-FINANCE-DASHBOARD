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
    alert: str | None = None  # "warning" or "danger" threshold crossed


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

        # Alert levels: warning at 80%, danger at 100%+
        alert = None
        if pct >= 100:
            alert = "danger"
        elif pct >= 80:
            alert = "warning"

        out.append(
            BudgetOut(
                category=b.category,
                limit_amount=b.limit_amount,
                spent=spent,
                remaining=remaining,
                pct=pct,
                alert=alert,  # type: ignore
            )
        )
    return out


@router.get("/alerts")
def get_budget_alerts(db: Session = Depends(get_db)):
    """Get categories that are at warning (80%) or danger (100%+) threshold."""
    spent_map = _spent_by_category(db)
    budgets = db.query(Budget).all()

    alerts = []
    for b in budgets:
        spent = round(spent_map.get(b.category, 0.0), 2)
        pct = round((spent / b.limit_amount * 100) if b.limit_amount > 0 else 0.0, 1)

        if pct >= 100:
            alerts.append(
                {
                    "category": b.category,
                    "level": "danger",
                    "spent": spent,
                    "limit": b.limit_amount,
                    "pct": pct,
                    "message": f"Over budget by ${spent - b.limit_amount:,.2f}",
                }
            )
        elif pct >= 80:
            alerts.append(
                {
                    "category": b.category,
                    "level": "warning",
                    "spent": spent,
                    "limit": b.limit_amount,
                    "pct": pct,
                    "message": f"Near limit — ${b.limit_amount - spent:,.2f} remaining",
                }
            )

    return alerts


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

    # Alert levels: warning at 80%, danger at 100%+
    alert = None
    if pct >= 100:
        alert = "danger"
    elif pct >= 80:
        alert = "warning"

    return BudgetOut(
        category=payload.category,
        limit_amount=payload.limit_amount,
        spent=spent,
        remaining=remaining,
        pct=pct,
        alert=alert,  # type: ignore
    )


@router.delete("/{category}")
def delete_budget(category: str, db: Session = Depends(get_db)):
    budget = db.query(Budget).filter(Budget.category == category).first()
    if budget:
        db.delete(budget)
        db.commit()
    return {"status": "deleted"}
