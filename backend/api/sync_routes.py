from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import SyncLog
from ..sync import sync_all

router = APIRouter()


def _bg_sync():
    """Background sync using its own DB session (avoids use-after-close on the request session)."""
    with SessionLocal() as db:
        sync_all(db, force_realtime=False)


@router.post("/trigger")
def trigger_sync(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    force_realtime: bool = Query(False, description="Fetch live balances ($0.10/account). Use for manual triggers only."),
):
    if force_realtime:
        # Run synchronously so the caller gets actual results back
        result = sync_all(db, force_realtime=True)
        return {"status": "completed", **result}
    else:
        background_tasks.add_task(_bg_sync)
        return {"status": "sync started"}


@router.get("/logs")
def get_sync_logs(limit: int = 20, db: Session = Depends(get_db)):
    logs = db.query(SyncLog).order_by(SyncLog.synced_at.desc()).limit(limit).all()
    return [
        {
            "id": log.id,
            "account_id": log.account_id,
            "institution": log.institution,
            "status": log.status,
            "transactions_added": log.transactions_added,
            "error_message": log.error_message,
            "synced_at": log.synced_at,
        }
        for log in logs
    ]
