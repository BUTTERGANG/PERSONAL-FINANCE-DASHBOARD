from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account

router = APIRouter()


class AccountOut(BaseModel):
    id: str
    name: str
    institution: str
    account_type: str
    balance: float
    available_balance: Optional[float]
    currency: str
    last_synced: Optional[datetime]
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return db.query(Account).filter(Account.is_active == True).order_by(Account.institution).all()


@router.delete("/{account_id}")
def deactivate_account(account_id: str, db: Session = Depends(get_db)):
    acct = db.get(Account, account_id)
    if acct:
        acct.is_active = False
        db.commit()
    return {"status": "deactivated"}
