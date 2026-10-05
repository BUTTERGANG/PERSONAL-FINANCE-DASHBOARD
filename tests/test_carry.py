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


def test_payoff_plan_single_debt(db):
    from backend.carry import payoff_plan

    debts = [{"id": 1, "name": "Card", "balance": 1200.0, "apr": 0.0, "min_payment": 100.0}]
    plan = payoff_plan(debts)
    assert plan["baseline"]["months"] == 12
    assert plan["baseline"]["total_interest"] == 0.0


def test_payoff_plan_apr_and_unpayable(db):
    from backend.carry import payoff_plan

    # 24% APR on $1,000: at $100/mo it takes more than 12 months and accrues interest.
    debts = [{"id": 1, "name": "Card", "balance": 1000.0, "apr": 24.0, "min_payment": 100.0}]
    plan = payoff_plan(debts)
    assert plan["baseline"]["months"] >= 12
    assert plan["baseline"]["total_interest"] > 0

    # Payment below monthly interest → never pays off.
    stuck = [{"id": 1, "name": "Card", "balance": 100000.0, "apr": 24.0, "min_payment": 100.0}]
    assert payoff_plan(stuck)["baseline"]["months"] is None


def test_payoff_avalanche_saves_interest(db):
    from backend.carry import payoff_plan

    debts = [
        {"id": 1, "name": "Low", "balance": 1000.0, "apr": 10.0, "min_payment": 50.0},
        {"id": 2, "name": "High", "balance": 1000.0, "apr": 30.0, "min_payment": 50.0},
    ]
    plan = payoff_plan(debts, extra=100.0)
    assert plan["avalanche"]["months"] < plan["baseline"]["months"]
    assert plan["interest_saved"] > 0
    # Highest APR debt is targeted first: cleared before the low-APR one.
    assert plan["avalanche"]["per_debt"][2] is not None


def test_extract_apr():
    from backend.pdf_parser import extract_apr

    chase = "Interest Charges\nAnnual Percentage Rate\nPurchase APR 22.24%\nCash Advance APR 29.99%"
    assert extract_apr(chase) == 22.24  # prefers purchase APR over cash advance
    assert extract_apr("APR for purchases is 21.74%") == 21.74
    assert extract_apr("no rates here") is None


def test_apply_statement_updates_debt(db):
    from fastapi.testclient import TestClient  # noqa: F401 — not used; direct logic instead

    from backend.api.carry import ApplyStatementIn, apply_statement

    seed_carry_items(db)
    db.add(CarryItem(name="Extra card", group="Credit Cards", monthly_low=50.0, is_debt=True))
    db.commit()
    item = db.query(CarryItem).filter(CarryItem.name == "Extra card").one()

    res = apply_statement(
        ApplyStatementIn(item_id=item.id, balance=812.44, min_payment=35.0, apr=21.74), db
    )
    assert res["balance"] == 812.44
    assert res["apr"] == 21.74
    db.refresh(item)
    assert item.balance == 812.44
    assert item.min_payment == 35.0
