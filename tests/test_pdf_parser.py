"""
PDF statement parser tests.

Each supported statement type gets one entry in STATEMENT_CASES with its
expected transaction count and section totals. A parse must:
  1. detect the right (bank, product),
  2. extract exactly the expected number of transactions,
  3. reconcile every section to the penny against the statement's printed totals,
  4. apply the right sign (money out = positive, money in = negative).

To add a new statement type: drop its sample PDF in tests/fixtures/statements/,
add a case here, and add its section config in backend/pdf_parser.py.
"""

from pathlib import Path

import pytest

from backend import pdf_parser as P

FIXTURES = Path(__file__).parent / "fixtures" / "statements"


class Case:
    def __init__(self, fixture, bank, product, count, sections, money_in, money_out,
                 account_balance=None, summary=None):
        self.fixture = fixture
        self.bank = bank
        self.product = product
        self.count = count
        self.sections = sections          # key -> printed total (abs magnitude)
        self.money_in = money_in          # count of negative-amount rows
        self.money_out = money_out        # count of positive-amount rows
        self.account_balance = account_balance   # expected ParseResult.account_balance
        self.summary = summary or {}      # subset of summary fields to assert


STATEMENT_CASES = [
    Case(
        fixture="chase_checking_2026-01.pdf",
        bank="chase", product="checking",
        count=62,
        sections={"deposits": 1153.46, "atm_debit": 719.81, "electronic": 1071.23},
        money_in=8, money_out=54,
        account_balance=146.81,
        summary={"beginning_balance": 784.39, "ending_balance": 146.81},
    ),
    Case(
        fixture="citi_credit_2026-01.pdf",
        bank="citi", product="credit",
        count=5,
        # Two-column layout (rewards column must be stripped) + header-bounded
        # sections + credit-card balance identity.
        sections={"payments": 350.00, "purchases": 6.41, "interest": 246.78},
        money_in=1, money_out=4,
        account_balance=13406.59,
        summary={
            "previous_balance": 13503.40, "new_balance": 13406.59,
            "minimum_payment_due": 380.78, "payment_due_date": "2026-02-22",
            "credit_limit": 14000.0, "available_credit": 593.0,
        },
    ),
    Case(
        fixture="paypal_credit_2026-01.pdf",
        bank="paypal", product="credit",
        count=4,
        # Single-column, explicit MM/DD/YY dates, printed signs. Section names are
        # repeated in the summary box → activity_anchor="CURRENT ACTIVITY" needed.
        sections={"payments": 120.00, "purchases": 45.47, "interest": 84.04},
        money_in=1, money_out=3,
        account_balance=3548.42,
        summary={
            "previous_balance": 3538.91, "new_balance": 3548.42,
            "minimum_payment_due": 119.00, "payment_due_date": "2026-02-18",
            "credit_limit": 4000.0, "available_credit": 451.0,
        },
    ),
    Case(
        fixture="venmo_credit_2026-02.pdf",
        bank="venmo", product="credit",
        count=2,
        # Synchrony layout. Bare MM/DD dates (period "... to ..." infers year),
        # "Previous balance as of DATE $amt" clause, and a $0.00 cash-advance
        # interest row that must be dropped (so count is 2, not 3).
        sections={"payments": 60.00, "interest": 34.25},
        money_in=1, money_out=1,
        account_balance=1627.10,
        summary={
            "previous_balance": 1652.85, "new_balance": 1627.10,
            "minimum_payment_due": 51.00, "payment_due_date": "2026-03-19",
            "credit_limit": 2100.0, "available_credit": 472.0,
        },
    ),
]

CASE_IDS = [f"{c.bank}_{c.product}" for c in STATEMENT_CASES]


@pytest.fixture(params=STATEMENT_CASES, ids=CASE_IDS)
def case(request):
    c = request.param
    path = FIXTURES / c.fixture
    if not path.exists():
        pytest.skip(f"fixture missing: {c.fixture}")
    return c, P.parse_statement(str(path))


def test_statement_type_detected(case):
    c, result = case
    assert result.bank == c.bank
    assert result.product == c.product
    assert result.method == "sectioned"


def test_transaction_count(case):
    c, result = case
    assert len(result.transactions) == c.count


def test_sections_reconcile_to_the_penny(case):
    c, result = case
    recon = result.reconciliation
    assert recon is not None
    assert recon.ok, f"reconciliation failed: {recon.notes}"
    for key, printed in c.sections.items():
        sec = recon.sections[key]
        assert sec["match"], f"{key}: parsed {sec['parsed']} != printed {sec['printed']}"
        assert abs(sec["printed"] - printed) < 0.01


def test_balance_check_passes(case):
    _, result = case
    assert result.reconciliation.balance_ok is True


def test_sign_convention(case):
    c, result = case
    money_in = [t for t in result.transactions if t["amount"] < 0]
    money_out = [t for t in result.transactions if t["amount"] > 0]
    assert len(money_in) == c.money_in
    assert len(money_out) == c.money_out


def test_all_transactions_wellformed(case):
    _, result = case
    for t in result.transactions:
        assert len(t["date"]) == 10 and t["date"][4] == "-"   # YYYY-MM-DD
        assert t["amount"] != 0
        assert t["description"].strip()


def test_no_duplicate_rows(case):
    _, result = case
    keys = [(t["date"], round(t["amount"], 2), t["description"][:50]) for t in result.transactions]
    assert len(keys) == len(set(keys))


def test_account_balance(case):
    c, result = case
    if c.account_balance is None:
        pytest.skip("no expected account balance")
    assert result.account_balance == pytest.approx(c.account_balance, abs=0.01)


def test_summary_fields(case):
    c, result = case
    if not c.summary:
        pytest.skip("no expected summary fields")
    for key, expected in c.summary.items():
        assert key in result.summary, f"missing summary field {key}"
        actual = result.summary[key]
        if isinstance(expected, float):
            assert actual == pytest.approx(expected, abs=0.01), f"{key}: {actual} != {expected}"
        else:
            assert actual == expected, f"{key}: {actual} != {expected}"


# ── Fidelity investment statement (structurally different: holdings, no txns) ────

FIDELITY_FIXTURE = "fidelity_investment_2026-04.pdf"


@pytest.fixture
def fidelity():
    path = FIXTURES / FIDELITY_FIXTURE
    if not path.exists():
        pytest.skip(f"fixture missing: {FIDELITY_FIXTURE}")
    return P.parse_statement(str(path))


def test_fidelity_detected_as_investment(fidelity):
    assert fidelity.bank == "fidelity"
    assert fidelity.product == "investment"
    assert fidelity.method == "investment"


def test_fidelity_no_transactions(fidelity):
    # Internal buys/reinvestments must NOT be imported as spending transactions.
    assert fidelity.transactions == []


def test_fidelity_account_value(fidelity):
    assert fidelity.account_balance == pytest.approx(1071.48, abs=0.01)
    assert fidelity.summary["beginning_value"] == pytest.approx(942.85, abs=0.01)


def test_fidelity_holdings(fidelity):
    assert len(fidelity.holdings) == 2
    by_symbol = {h.symbol: h for h in fidelity.holdings}
    assert by_symbol["SPAXX"].market_value == pytest.approx(574.28, abs=0.01)
    assert by_symbol["DBB"].market_value == pytest.approx(497.20, abs=0.01)
    # cost basis / unrealized parsed where present; "not applicable" → None.
    assert by_symbol["SPAXX"].cost_basis is None
    assert by_symbol["DBB"].cost_basis == pytest.approx(420.98, abs=0.01)
    assert by_symbol["DBB"].unrealized_gain == pytest.approx(76.22, abs=0.01)


def test_fidelity_holdings_reconcile_to_account_value(fidelity):
    assert fidelity.reconciliation.ok
    holdings_sum = sum(h.market_value for h in fidelity.holdings)
    assert holdings_sum == pytest.approx(fidelity.account_balance, abs=0.01)


# ── Fidelity CRYPTO statement (separate monthly statement, different layout) ─────

FIDELITY_CRYPTO_FIXTURE = "fidelity_crypto_2026-04.pdf"


@pytest.fixture
def fidelity_crypto():
    path = FIXTURES / FIDELITY_CRYPTO_FIXTURE
    if not path.exists():
        pytest.skip(f"fixture missing: {FIDELITY_CRYPTO_FIXTURE}")
    return P.parse_statement(str(path))


def test_crypto_detected_as_crypto(fidelity_crypto):
    assert fidelity_crypto.bank == "fidelity"
    assert fidelity_crypto.product == "crypto"
    assert fidelity_crypto.transactions == []


def test_crypto_account_value(fidelity_crypto):
    assert fidelity_crypto.account_balance == pytest.approx(180.50, abs=0.01)
    assert fidelity_crypto.summary["beginning_value"] == pytest.approx(159.38, abs=0.01)


def test_crypto_holdings(fidelity_crypto):
    # $0.00 USD cash line is dropped; only Bitcoin remains.
    assert len(fidelity_crypto.holdings) == 1
    btc = fidelity_crypto.holdings[0]
    assert btc.symbol == "BTC"
    assert btc.market_value == pytest.approx(180.50, abs=0.01)
    assert btc.quantity == pytest.approx(0.00235744, abs=1e-8)
    assert btc.cost_basis == pytest.approx(200.00, abs=0.01)
    # Underwater position — unrealized loss must keep its negative sign.
    assert btc.unrealized_gain == pytest.approx(-19.50, abs=0.01)


def test_crypto_holdings_reconcile(fidelity_crypto):
    assert fidelity_crypto.reconciliation.ok
    holdings_sum = sum(h.market_value for h in fidelity_crypto.holdings)
    assert holdings_sum == pytest.approx(fidelity_crypto.account_balance, abs=0.01)
