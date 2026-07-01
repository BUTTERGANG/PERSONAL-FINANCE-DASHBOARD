from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import IgnoredSubscription
from ..subscriptions import detect_subscriptions

router = APIRouter()


class IgnoreRequest(BaseModel):
    merchant_key: str


@router.get("/")
def list_subscriptions(db: Session = Depends(get_db)):
    return detect_subscriptions(db)


@router.post("/ignore")
def ignore_subscription(payload: IgnoreRequest, db: Session = Depends(get_db)):
    key = payload.merchant_key.strip().lower()
    if key and not db.query(IgnoredSubscription).filter(IgnoredSubscription.merchant_key == key).first():
        db.add(IgnoredSubscription(merchant_key=key))
        db.commit()
    return {"status": "ignored", "merchant_key": key}


@router.delete("/ignore/{merchant_key}")
def unignore_subscription(merchant_key: str, db: Session = Depends(get_db)):
    key = merchant_key.strip().lower()
    row = db.query(IgnoredSubscription).filter(IgnoredSubscription.merchant_key == key).first()
    if row:
        db.delete(row)
        db.commit()
    return {"status": "unignored", "merchant_key": key}
