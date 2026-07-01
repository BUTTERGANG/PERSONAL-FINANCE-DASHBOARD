"""
Dev-only seed data — populates finance.db with fake accounts, ~120 days of
transactions (including obvious subscriptions), and a net-worth trend so all
four dashboard features render without real Plaid/Fidelity credentials.

Usage (from the repo root):
    python scripts/seed_dev_data.py

Safe to re-run: it removes its own previously-seeded rows (id prefix "seed-")
before inserting. It never touches real linked accounts or their transactions.
"""

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import SessionLocal, init_db
from backend.models import CREDIT_TYPES, Account, NetWorthSnapshot, Transaction

_UTC = timezone.utc
random.seed(42)  # deterministic seed data

SEED_PREFIX = "seed-"

ACCOUNTS = [
    {"id": "seed-chase", "name": "Chase Checking", "institution": "chase", "account_type": "checking", "balance": 4213.55},
    {"id": "seed-citi", "name": "Citi Double Cash", "institution": "citi", "account_type": "credit", "balance": 1342.18},
    {"id": "seed-fidelity", "name": "Fidelity Brokerage", "institution": "fidelity", "account_type": "investment", "balance": 28940.00},
]

# Recurring charges the detector should catch (monthly cadence, stable amount).
SUBSCRIPTIONS = [
    {"merchant": "Netflix", "amount": 15.99, "category": "Entertainment", "account_id": "seed-chase"},
    {"merchant": "Spotify", "amount": 10.99, "category": "Entertainment", "account_id": "seed-chase"},
    {"merchant": "Planet Fitness", "amount": 24.99, "category": "Health and Fitness", "account_id": "seed-citi"},
]

# One-off / irregular spend so the detector has noise to reject.
ONE_OFFS = [
    ("Whole Foods", "Groceries", 60, 140),
    ("Shell Gas", "Travel", 30, 70),
    ("Amazon", "Shopping", 12, 95),
    ("Chipotle", "Food and Drink", 9, 22),
]


def _clear_seed(db):
    db.query(Transaction).filter(Transaction.id.like(f"{SEED_PREFIX}%")).delete(synchronize_session=False)
    db.query(Account).filter(Account.id.like(f"{SEED_PREFIX}%")).delete(synchronize_session=False)
    db.query(NetWorthSnapshot).delete(synchronize_session=False)
    db.commit()


def _seed_accounts(db):
    for a in ACCOUNTS:
        db.add(Account(**a, currency="USD", is_active=True, last_synced=datetime.now(_UTC)))
    db.commit()


def _seed_transactions(db):
    today = datetime.now(_UTC)
    n = 0
    # Monthly subscriptions across the last ~4 months. The most recent occurrence
    # (month=0) is dated today so there's always current-month spend for budgets.
    for sub in SUBSCRIPTIONS:
        for month in range(4):
            when = today - timedelta(days=30 * month)
            db.add(Transaction(
                id=f"{SEED_PREFIX}{sub['merchant'].lower().replace(' ', '')}-{month}",
                account_id=sub["account_id"],
                date=when,
                amount=sub["amount"],
                description=sub["merchant"],
                category=sub["category"],
                merchant=sub["merchant"],
                pending=False,
                source="plaid",
            ))
            n += 1
    # Scattered one-off spend over the last 120 days.
    for i in range(60):
        merchant, category, lo, hi = random.choice(ONE_OFFS)
        when = today - timedelta(days=random.randint(0, 120))
        db.add(Transaction(
            id=f"{SEED_PREFIX}oneoff-{i}",
            account_id=random.choice(["seed-chase", "seed-citi"]),
            date=when,
            amount=round(random.uniform(lo, hi), 2),
            description=merchant,
            category=category,
            merchant=merchant,
            pending=False,
            source="plaid",
        ))
        n += 1
    db.commit()
    return n


def _seed_snapshots(db):
    """Build a 30-day net-worth trend so the Overview line chart renders."""
    accounts = db.query(Account).filter(Account.is_active == True).all()
    assets = sum(a.balance for a in accounts if a.account_type not in CREDIT_TYPES)
    debts = sum(a.balance for a in accounts if a.account_type in CREDIT_TYPES)
    base = assets - debts

    today = datetime.now(_UTC)
    for d in range(30, -1, -1):
        day_dt = today - timedelta(days=d)
        # Gentle upward drift + small noise so the line looks real.
        nw = round(base - d * 45 + random.uniform(-120, 120), 2)
        db.add(NetWorthSnapshot(
            day=day_dt.strftime("%Y-%m-%d"),
            captured_at=day_dt,
            net_worth=nw,
            total_assets=round(assets, 2),
            total_debt=round(debts, 2),
            breakdown_json=json.dumps({a.institution: a.balance for a in accounts}),
        ))
    db.commit()


def main():
    init_db()
    db = SessionLocal()
    try:
        _clear_seed(db)
        _seed_accounts(db)
        txn_count = _seed_transactions(db)
        _seed_snapshots(db)
        print(f"Seeded {len(ACCOUNTS)} accounts, {txn_count} transactions, 31 net-worth snapshots.")
        print("Subscriptions to detect: Netflix, Spotify, Planet Fitness.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
