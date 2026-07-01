"""
FastAPI application entry point.
Starts APScheduler for background sync on startup.
"""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import accounts, budgets, networth, plaid_routes, subscriptions, sync_routes, transactions
from .config import get_settings
from .database import SessionLocal, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
_scheduler = BackgroundScheduler(timezone="UTC")


def _run_scheduled_sync():
    from .sync import sync_all
    db = SessionLocal()
    try:
        result = sync_all(db)
        logger.info("Scheduled sync complete: %s", result)
    except Exception as exc:
        logger.error("Scheduled sync error: %s", exc)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized.")

    _scheduler.add_job(
        _run_scheduled_sync,
        trigger="interval",
        hours=settings.sync_interval_hours,
        id="auto_sync",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started — syncing every %sh.", settings.sync_interval_hours)

    yield

    _scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")


app = FastAPI(
    title="Personal Finance Dashboard API",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_base_url, "http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
app.include_router(plaid_routes.router, prefix="/api/plaid", tags=["plaid"])
app.include_router(sync_routes.router, prefix="/api/sync", tags=["sync"])
app.include_router(networth.router, prefix="/api/networth", tags=["networth"])
app.include_router(budgets.router, prefix="/api/budgets", tags=["budgets"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["subscriptions"])


@app.get("/health")
def health():
    return {"status": "ok", "sync_interval_hours": settings.sync_interval_hours}
