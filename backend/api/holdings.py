from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import holdings as holdings_logic
from ..database import get_db
from ..models import Holding

router = APIRouter()


@router.get("/")
def list_holdings(account_id: str | None = None, db: Session = Depends(get_db)):
    """Every persisted position (optionally scoped to one account), newest first."""
    q = db.query(Holding)
    if account_id:
        q = q.filter(Holding.account_id == account_id)
    rows = q.order_by(Holding.market_value.desc()).all()
    return [holdings_logic._holding_row(h, h.account_id) for h in rows]


@router.get("/portfolio")
def get_portfolio(db: Session = Depends(get_db)):
    """All positions grouped by account, with per-account and grand totals."""
    return holdings_logic.portfolio(db)


@router.delete("/{holding_id}")
def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    h = db.get(Holding, holding_id)
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found.")
    db.delete(h)
    db.commit()
    return {"ok": True, "id": holding_id}
