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


class CarryItemPatch(BaseModel):
    name: str | None = None
    group: str | None = None
    monthly_low: float | None = None
    monthly_high: float | None = None
    merchant_keywords: str | None = None
    category: str | None = None
    sort_order: int | None = None


@router.get("/")
def get_carry(month: str | None = None, db: Session = Depends(get_db)):
    """Fixed vs actual monthly carry for one month (`month=YYYY-MM`)."""
    summary = carry_logic.carry_summary(db, month)
    summary["trend"] = carry_logic.recent_month_actuals(db)
    return summary


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
