from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import NetWorthSnapshot

router = APIRouter()

_UTC = timezone.utc


class SnapshotOut(BaseModel):
    day: str
    net_worth: float
    total_assets: float
    total_debt: float

    model_config = {"from_attributes": True}


@router.get("/snapshots", response_model=list[SnapshotOut])
def list_snapshots(days: int = Query(default=90, ge=1, le=1825), db: Session = Depends(get_db)):
    """Net worth history for the trend chart, oldest first, limited to the last N days."""
    since = (datetime.now(_UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    return (
        db.query(NetWorthSnapshot)
        .filter(NetWorthSnapshot.day >= since)
        .order_by(NetWorthSnapshot.day.asc())
        .all()
    )
