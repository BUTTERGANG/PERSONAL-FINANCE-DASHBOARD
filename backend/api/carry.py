from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import carry as carry_logic
from ..database import get_db
from ..models import CarryItem

router = APIRouter()


class CarryItemIn(BaseModel):
    name: str
    group: str = "Other"
    monthly_low: float
    monthly_high: float | None = None
    merchant_keywords: str | None = None
    category: str | None = None
    sort_order: int = 0
    is_debt: bool = False
    balance: float | None = None
    apr: float | None = None
    min_payment: float | None = None


class CarryItemPatch(BaseModel):
    name: str | None = None
    group: str | None = None
    monthly_low: float | None = None
    monthly_high: float | None = None
    merchant_keywords: str | None = None
    category: str | None = None
    sort_order: int | None = None
    is_debt: bool | None = None
    balance: float | None = None
    apr: float | None = None
    min_payment: float | None = None


@router.get("/")
def get_carry(month: str | None = None, db: Session = Depends(get_db)):
    """Fixed vs actual monthly carry for one month (`month=YYYY-MM`)."""
    summary = carry_logic.carry_summary(db, month)
    summary["trend"] = carry_logic.recent_month_actuals(db)
    return summary


@router.get("/payoff")
def get_payoff(extra: float = 0.0, db: Session = Depends(get_db)):
    """
    Debt payoff calculator. Debts are carry items flagged is_debt with a
    balance set. `extra` is an additional monthly payment applied avalanche
    style (highest APR first).
    """
    from .. import carry as carry_logic

    carry_logic.seed_carry_items(db)
    debts = [
        {
            "id": it.id,
            "name": it.name,
            "balance": float(it.balance),
            "apr": float(it.apr or 0.0),
            "min_payment": float(it.min_payment or 0.0),
        }
        for it in db.query(CarryItem).filter(CarryItem.is_debt == True).all()  # noqa: E712
        if it.balance and it.balance > 0 and it.apr and (it.min_payment or 0) > 0
    ]
    missing = [
        it.name
        for it in db.query(CarryItem).filter(CarryItem.is_debt == True).all()  # noqa: E712
        if not (it.balance and it.balance > 0)
    ]
    plan = carry_logic.payoff_plan(debts, extra) if debts else None
    return {"debts": debts, "missing_balance": missing, "plan": plan}


@router.post("/", status_code=201)
def add_carry_item(payload: CarryItemIn, db: Session = Depends(get_db)):
    if db.query(CarryItem).filter(CarryItem.name == payload.name).first():
        raise HTTPException(status_code=409, detail="An item with that name already exists.")
    item = CarryItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "name": item.name}


@router.patch("/{item_id}")
def update_carry_item(item_id: int, payload: CarryItemPatch, db: Session = Depends(get_db)):
    item = db.get(CarryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Carry item not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    return {"ok": True, "id": item.id}


@router.delete("/{item_id}")
def delete_carry_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(CarryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Carry item not found.")
    db.delete(item)
    db.commit()
    return {"ok": True}
