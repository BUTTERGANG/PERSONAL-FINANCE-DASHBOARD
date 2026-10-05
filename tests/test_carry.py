"""Monthly carry: seeding, actuals-from-transactions, summary totals."""

import pytest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.carry import carry_summary, seed_carry_items
from backend.models import Base, CarryItem, Transaction

_UTC = timezone.utc


@pytest.fixture()
def db():
    # Isolated in-memory DB — never touch the real finance.db.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


_txn_seq = iter(range(10000))


def _txn(db, amount, description, day, merchant=None, category=None, pending=False):
    db.add(
        Transaction(
            id=f"t-{next(_txn_seq)}",
            account_id="acc1",
            date=datetime(2026, 10, day, tzinfo=_UTC),
            amount=amount,
            description=description,
            merchant=merchant,
            category=category,
            pending=pending,
            source="csv",
        )
    )
    db.commit()  # sessions use autoflush=False — make rows visible to queries


def test_seed_is_idempotent_and_matches_spec_totals(db):
    assert seed_carry_items(db) == 12
    assert seed_carry_items(db) == 0  # re-seed adds nothing
    summary = carry_summary(db)
    t = summary["totals"]
    assert t["monthly_low"] == pytest.approx(1353.10)
    assert t["monthly_high"] == pytest.approx(1373.10)
    assert t["quarter_low"] == pytest.approx(4059.30)
    assert t["quarter_high"] == pytest.approx(4119.30)


def test_openrouter_range(db):
    summary = carry_summary(db)
    item = next(i for i in summary["items"] if "OpenRouter" in i["name"])
    assert item["monthly_low"] == 30.00
    assert item["monthly_high"] == 50.00


def test_actuals_by_merchant_keyword(db):
    seed_carry_items(db)
    _txn(db, 75.00, "ADOBE  Creative Cloud", 3, merchant="Adobe")
    _txn(db, 227.40, "SHELL OIL 5746", 5)
    _txn(db, 500.00, "PAYMENT TO CHASE CARD", 10, merchant="Chase Card")
    _txn(db, 500.00, "PAYMENT TO CHASE CARD", 11, merchant="Chase Card")  # double-posted month
    summary = carry_summary(db, month="2026-10")
    items = {i["name"]: i for i in summary["items"]}
    assert items["Adobe Creative Cloud"]["actual"] == 75.00
    assert items["City credit card"]["actual"] == 1000.00
    assert items["Fuel"]["actual"] == 227.40


def test_pending_transactions_excluded(db):
    seed_carry_items(db)
    _txn(db, 110.00, "PROGRESSIVE INSURANCE", 4, pending=True)
    summary = carry_summary(db, month="2026-10")
    item = next(i for i in summary["items"] if i["name"] == "Car insurance")
    assert item["actual"] == 0.0


def test_month_scoping(db):
    seed_carry_items(db)
    _txn(db, 25.00, "REPLIT MONTHLY", 3)
    db.add(
        Transaction(
            id="t-nov",
            account_id="acc1",
            date=datetime(2026, 11, 3, tzinfo=_UTC),
            amount=25.00,
            description="REPLIT MONTHLY",
            source="csv",
        )
    )
    db.commit()
    oct_summary = carry_summary(db, month="2026-10")
    nov_summary = carry_summary(db, month="2026-11")
    oct_replit = next(i for i in oct_summary["items"] if i["name"] == "Replit")
    nov_replit = next(i for i in nov_summary["items"] if i["name"] == "Replit")
    assert oct_replit["actual"] == 25.00
    assert nov_replit["actual"] == 25.00


def test_category_fallback_when_no_keywords(db):
    db.add(
        CarryItem(
            name="Misc travel",
            group="Other",
            monthly_low=50.0,
            category="Travel",
            sort_order=999,
        )
    )
    _txn(db, 62.10, "DELTA AIR LINES", 7, category="Travel")
    summary = carry_summary(db, month="2026-10")
    item = next(i for i in summary["items"] if i["name"] == "Misc travel")
    assert item["actual"] == 62.10
