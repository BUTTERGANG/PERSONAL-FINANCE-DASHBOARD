"""Holdings: position keys, upsert (idempotent re-import), portfolio aggregation."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.holdings import position_key, upsert_holdings, portfolio
from backend.models import Account, Base, Holding


@pytest.fixture()
def db():
    # StaticPool keeps ONE connection, so the in-memory schema is visible to the
    # worker thread TestClient runs endpoints on (a plain sqlite:// memory DB is
    # per-connection and would appear empty there).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _account(db, account_id="manual-fidelity", name="Fidelity"):
    db.add(Account(id=account_id, name=name, institution="fidelity",
                   account_type="investment", balance=0.0))
    db.commit()
    return account_id


def _row(symbol, desc, qty, price, mv, cb=None, gain=None):
    return {
        "symbol": symbol, "description": desc, "quantity": qty, "price": price,
        "market_value": mv, "cost_basis": cb, "unrealized_gain": gain,
    }


def test_position_key_prefers_symbol_then_slug():
    assert position_key("vti", "Vanguard Total Stock") == "VTI"
    assert position_key(None, "Fidelity Money Market (SPAXX)") == "fidelity-money-market-spaxx"
    assert position_key("", "  ") == "position"  # never empty


def test_period_end_label_formats_and_handles_none():
    from backend.pdf_parser import Period, period_end_label

    assert period_end_label(Period(9, 2026, 9, 2026)) == "2026-09"
    assert period_end_label(Period(12, 2025, 1, 2026)) == "2026-01"
    assert period_end_label(None) is None


def test_upsert_inserts_positions(db):
    acct = _account(db)
    res = upsert_holdings(db, acct, [
        _row("VTI", "Vanguard Total", 10, 250.0, 2500.0, 2000.0),
        _row(None, "Fidelity Money Market", None, 1.0, 500.0),
    ], as_of="2026-09-30")
    db.commit()
    assert res == {"added": 2, "updated": 0, "total": 2}
    assert db.query(Holding).count() == 2


def test_reimport_updates_in_place_not_duplicates(db):
    acct = _account(db)
    upsert_holdings(db, acct, [_row("VTI", "Vanguard Total", 10, 250.0, 2500.0, 2000.0)])
    db.commit()
    # A later statement: same ticker, new quantity/value → same row, refreshed.
    res = upsert_holdings(db, acct, [_row("VTI", "Vanguard Total Stock", 12, 260.0, 3120.0, 2400.0)],
                          as_of="2026-10-31")
    db.commit()
    assert res == {"added": 0, "updated": 1, "total": 1}
    assert db.query(Holding).count() == 1
    h = db.query(Holding).one()
    assert h.quantity == 12 and h.market_value == 3120.0 and h.as_of == "2026-10-31"


def test_reimport_without_a_field_does_not_wipe_it(db):
    """A later statement missing a column must not blank out what we already know."""
    acct = _account(db)
    upsert_holdings(db, acct, [_row("VTI", "Vanguard Total", 10, 250.0, 2500.0, 2000.0, gain=500.0)])
    db.commit()
    upsert_holdings(db, acct, [{"description": "Vanguard Total", "symbol": "VTI",
                                "market_value": 2600.0}])
    db.commit()
    h = db.query(Holding).one()
    assert h.unrealized_gain == 500.0   # survived
    assert h.cost_basis == 2000.0       # survived
    assert h.market_value == 2600.0     # refreshed


def test_row_gain_matches_totals(db):
    """A position row reports the same effective gain the totals sum."""
    acct = _account(db)
    upsert_holdings(db, acct, [_row("VTI", "Vanguard Total", 10, 250.0, 2500.0, 2000.0)])
    db.commit()
    p = portfolio(db)
    row = p["accounts"][0]["holdings"][0]
    assert row["unrealized_gain"] == pytest.approx(500.0)      # market − cost
    assert p["totals"]["unrealized_gain"] == pytest.approx(500.0)


def test_blank_description_skipped(db):
    acct = _account(db)
    res = upsert_holdings(db, acct, [{"description": "  ", "market_value": 10.0}])
    assert res["total"] == 0
    assert db.query(Holding).count() == 0


def test_portfolio_totals_and_gain_fallback(db):
    acct = _account(db)
    upsert_holdings(db, acct, [
        _row("VTI", "Vanguard Total", 10, 250.0, 2500.0, 2000.0),          # gain from mv−cb = 500
        _row("NVDA", "Nvidia", 2, 500.0, 1000.0, 800.0, gain=250.0),        # gain stated = 250
        _row(None, "Money Market", None, 1.0, 500.0),                       # no cost basis → no gain
    ])
    db.commit()
    p = portfolio(db)
    assert p["totals"]["positions"] == 3
    assert p["totals"]["market_value"] == pytest.approx(4000.0)
    assert p["totals"]["cost_basis"] == pytest.approx(2800.0)
    assert p["totals"]["unrealized_gain"] == pytest.approx(750.0)  # 500 + 250
    assert p["totals"]["return_pct"] == pytest.approx(26.79, abs=0.01)
    # Positions inside an account are sorted by market value, descending.
    assert [h["symbol"] for h in p["accounts"][0]["holdings"]] == ["VTI", "NVDA", None]


def test_portfolio_groups_by_account(db):
    a1 = _account(db, "manual-fidelity", "Fidelity")
    a2 = _account(db, "manual-coinbase", "Coinbase")
    upsert_holdings(db, a1, [_row("VTI", "Vanguard Total", 1, 250.0, 250.0, 200.0)])
    upsert_holdings(db, a2, [_row("BTC", "Bitcoin", 0.01, 60000.0, 600.0)])
    db.commit()
    p = portfolio(db)
    assert len(p["accounts"]) == 2
    # Highest market value account first (Coinbase 600 > Fidelity 250).
    assert p["accounts"][0]["account_name"] == "Coinbase"
    assert p["accounts"][0]["account_id"] == a2
    assert p["totals"]["positions"] == 2
    assert p["totals"]["market_value"] == pytest.approx(850.0)


def test_confirm_persists_holdings_and_portfolio_serves_them(db):
    """End-to-end through the API: import-pdf/confirm stores positions, the
    holdings router reads them back."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api import holdings as holdings_api
    from backend.api import manual as manual_api
    from backend.database import get_db

    _account(db)  # manual-fidelity, so positions have somewhere to land

    def _override():
        yield db

    # Isolated app over just the two routers — no PIN middleware, no global engine.
    test_app = FastAPI()
    test_app.include_router(manual_api.router, prefix="/api/manual")
    test_app.include_router(holdings_api.router, prefix="/api/holdings")
    test_app.dependency_overrides[get_db] = _override

    client = TestClient(test_app)
    resp = client.post(
        "/api/manual/import-pdf/confirm",
        json={
            "account_id": "manual-fidelity",
            "holdings": [_row("VTI", "Vanguard Total", 10, 250.0, 2500.0, 2000.0)],
            "as_of": "2026-09-30",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["holdings_added"] == 1
    assert body["added"] == 0  # holdings-only statement

    port = client.get("/api/holdings/portfolio").json()
    assert port["totals"]["positions"] == 1
    assert port["totals"]["market_value"] == pytest.approx(2500.0)
    assert port["accounts"][0]["holdings"][0]["symbol"] == "VTI"
    assert port["accounts"][0]["holdings"][0]["as_of"] == "2026-09-30"

    # Re-import the same statement → updated in place, not duplicated.
    resp2 = client.post(
        "/api/manual/import-pdf/confirm",
        json={"account_id": "manual-fidelity",
              "holdings": [_row("VTI", "Vanguard Total", 10, 250.0, 2500.0, 2000.0)]},
    )
    assert resp2.json()["holdings_updated"] == 1
    assert len(client.get("/api/holdings/").json()) == 1

