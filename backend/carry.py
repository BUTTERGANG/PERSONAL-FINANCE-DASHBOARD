"""
Monthly carry: fixed/estimated recurring obligations plus actuals computed
from the transactions table (imported CSV/PDF statements).

The seed data is the user's Oct–Dec 2026 estimate. Seeding is idempotent:
rows are matched by name and only inserted when missing, so user edits to
amounts survive re-seeds.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import CarryItem, Transaction

_UTC = timezone.utc

# Editable default APR applied to seeded debt items. Statement APRs override
# this — the user updates it from the invoice whenever it changes.
DEFAULT_CC_APR = 22.25

# (name, group, monthly_low, monthly_high, merchant_keywords, category, sort,
#  is_debt, min_payment)
SEED_ITEMS = [
    ("City credit card", "Credit Cards", 500.00, None, "chase", "Payment", 10, True, 500.00),
    ("Venmo credit card", "Credit Cards", 100.00, None, "venmo", "Payment", 20, True, 100.00),
    ("PayPal credit", "Credit Cards", 120.00, None, "paypal", "Payment", 30, True, 120.00),
    ("Fuel", "Transport", 303.10, None, "shell,speedway,marathon,bp,exxon,amoco,thorntons,casey,circle k,getgo,rita", None, 40, False, None),
    ("Car insurance", "Insurance", 110.00, None, "progressive,geico,state farm,allstate,insurance", None, 50, False, None),
    ("Adobe Creative Cloud", "Software", 75.00, None, "adobe", "Subscriptions", 60, False, None),
    ("Claude Pro (2 accounts)", "Software", 40.00, None, "claude,anthropic", "Subscriptions", 70, False, None),
    ("OpenRouter credits", "Software", 30.00, 50.00, "openrouter", "Subscriptions", 80, False, None),
    ("Replit", "Software", 25.00, None, "replit", "Subscriptions", 90, False, None),
    ("Google Workspace", "Software", 20.00, None, "google workspace,google llc,google one", "Subscriptions", 100, False, None),
    ("Dropbox", "Software", 15.00, None, "dropbox", "Subscriptions", 110, False, None),
    ("Frame.io", "Software", 15.00, None, "frame.io,frameio", "Subscriptions", 120, False, None),
]


def _ensure_debt_columns(db: Session) -> None:
    """
    Lightweight migration: create_all() only creates missing TABLES, not missing
    COLUMNS — so the pre-debt-fields carry_items table gets its new columns here.
    """
    from sqlalchemy import text

    existing = {
        row[1] for row in db.execute(text("PRAGMA table_info(carry_items)")).fetchall()
    }
    wanted = {
        "balance": "REAL",
        "apr": "REAL",
        "min_payment": "REAL",
        "is_debt": "BOOLEAN DEFAULT 0",
    }
    for col, ddl in wanted.items():
        if col not in existing:
            db.execute(text(f"ALTER TABLE carry_items ADD COLUMN {col} {ddl}"))
    db.commit()


def seed_carry_items(db: Session) -> int:
    """Insert any missing seed items. Returns how many were added."""
    _ensure_debt_columns(db)
    existing = {name for (name,) in db.query(CarryItem.name).all()}
    added = 0
    for name, group, low, high, keywords, category, sort, is_debt, min_payment in SEED_ITEMS:
        if name in existing:
            continue
        db.add(
            CarryItem(
                name=name,
                group=group,
                monthly_low=low,
                monthly_high=high,
                merchant_keywords=keywords,
                category=category,
                is_debt=is_debt,
                apr=DEFAULT_CC_APR if is_debt else None,
                min_payment=min_payment,
                sort_order=sort,
            )
        )
        added += 1
    if added:
        db.commit()

    # Backfill: pre-debt-field rows of the seeded card items become debts once
    # (only when never user-edited — untouched rows still have apr IS NULL).
    untouched_cards = (
        db.query(CarryItem)
        .filter(
            CarryItem.name.in_(["City credit card", "Venmo credit card", "PayPal credit"]),
            CarryItem.is_debt == False,  # noqa: E712
            CarryItem.apr == None,  # noqa: E711
        )
        .all()
    )
    if untouched_cards:
        for it in untouched_cards:
            it.is_debt = True
            it.apr = DEFAULT_CC_APR
            it.min_payment = it.monthly_low
        db.commit()
    return added


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=_UTC)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=_UTC)
    else:
        end = datetime(year, month + 1, 1, tzinfo=_UTC)
    return start, end


def _parse_year_month(value: str | None) -> tuple[int, int]:
    """'YYYY-MM' → (year, month); None/invalid → current month (UTC)."""
    if value:
        try:
            parts = value.split("-")
            year, month = int(parts[0]), int(parts[1])
            if 1 <= month <= 12:
                return year, month
        except (ValueError, IndexError):
            pass
    now = datetime.now(_UTC)
    return now.year, now.month


def _item_matches(item: CarryItem, description: str, merchant: str | None) -> bool:
    haystack = f"{merchant or ''} {description}".lower()
    if item.merchant_keywords:
        for kw in item.merchant_keywords.split(","):
            kw = kw.strip().lower()
            if kw and kw in haystack:
                return True
    if item.category:
        return False  # category matching handled by the query, not per-row
    return False


def actual_for_item(db: Session, item: CarryItem, year: int, month: int) -> float:
    """
    Actual spend for one carry item in a calendar month, from imported
    transactions. Merchant-keyword matches take priority; otherwise the item's
    category is used. Excludes pending rows (statement amounts can post twice).
    """
    start, end = _month_bounds(year, month)

    def _sum(match):
        row = (
            db.query(func.sum(Transaction.amount))
            .filter(
                Transaction.date >= start,
                Transaction.date < end,
                Transaction.amount > 0,
                Transaction.pending == False,  # noqa: E712
                match,
            )
            .scalar()
        )
        return float(row or 0.0)

    if item.merchant_keywords:
        keyword_total = 0.0
        from sqlalchemy import or_

        clauses = []
        for kw in item.merchant_keywords.split(","):
            kw = kw.strip()
            if kw:
                clauses.append(Transaction.description.ilike(f"%{kw}%"))
                clauses.append(Transaction.merchant.ilike(f"%{kw}%"))
        if clauses:
            keyword_total = _sum(or_(*clauses))
        if keyword_total > 0:
            return round(keyword_total, 2)

    if item.category:
        return round(_sum(Transaction.category == item.category), 2)
    return 0.0


def carry_summary(db: Session, month: str | None = None, months_back: int = 3) -> dict:
    """
    Full monthly-carry view: per-item fixed vs actual, plus totals for the
    selected month and a trailing `months_back`-month projection (fixed only —
    the carry is what you KNOW you owe).
    """
    year, month = _parse_year_month(month)
    seed_carry_items(db)
    items = db.query(CarryItem).order_by(CarryItem.sort_order, CarryItem.name).all()

    out_items = []
    total_low = 0.0
    total_high = 0.0
    total_actual = 0.0
    for it in items:
        low = it.monthly_low
        high = it.monthly_high if it.monthly_high is not None else it.monthly_low
        actual = actual_for_item(db, it, year, month)
        total_low += low
        total_high += high
        total_actual += actual
        out_items.append(
            {
                "id": it.id,
                "name": it.name,
                "group": it.group,
                "monthly_low": round(low, 2),
                "monthly_high": round(high, 2),
                "actual": actual,
                "variance": round(actual - high, 2) if it.monthly_high is not None else round(actual - low, 2),
                "merchant_keywords": it.merchant_keywords or "",
                "category": it.category,
                "sort_order": it.sort_order,
                "is_debt": bool(it.is_debt),
                "balance": it.balance,
                "apr": it.apr,
                "min_payment": it.min_payment,
            }
        )

    return {
        "month": f"{year:04d}-{month:02d}",
        "items": out_items,
        "totals": {
            "monthly_low": round(total_low, 2),
            "monthly_high": round(total_high, 2),
            "monthly_actual": round(total_actual, 2),
            "quarter_low": round(total_low * months_back, 2),
            "quarter_high": round(total_high * months_back, 2),
            "quarter_months": months_back,
        },
    }


def recent_month_actuals(db: Session, months: int = 6) -> list[dict]:
    """Total actual carry-relevant spend per month for the trend sparkline."""
    now = datetime.now(_UTC)
    out = []
    for i in range(months - 1, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        start, end = _month_bounds(y, m)
        row = (
            db.query(func.sum(Transaction.amount))
            .filter(
                Transaction.date >= start,
                Transaction.date < end,
                Transaction.amount > 0,
                Transaction.pending == False,  # noqa: E712
            )
            .scalar()
        )
        out.append({"month": f"{y:04d}-{m:02d}", "spend": round(float(row or 0.0), 2)})
    return out


# --- Debt payoff calculator -------------------------------------------------

_MAX_MONTHS = 600  # 50-year cap: anything longer is reported as "not payable"


def _payoff_months(balance: float, apr: float, payment: float) -> tuple[int, float] | None:
    """
    Amortize one debt. Returns (months, total_interest) or None if the payment
    can't cover the monthly interest (balance never shrinks).
    """
    r = apr / 100.0 / 12.0
    bal = balance
    interest_total = 0.0
    months = 0
    while bal > 0 and months < _MAX_MONTHS:
        interest = bal * r
        interest_total += interest
        principal = payment - interest
        if principal <= 0:
            return None
        bal -= principal
        months += 1
    return (months, round(interest_total, 2)) if bal <= 0 else None


def payoff_plan(debts: list[dict], extra: float = 0.0) -> dict:
    """
    debts: [{id, name, balance, apr, min_payment}] — all balances > 0.
    Baseline: each debt paid at its own minimum (extra is NOT applied).
    Avalanche: extra is applied each month to the highest-APR debt while the
    others pay minimum; freed minimums roll onto the next-highest APR debt.
    """
    from datetime import date

    def _month_add(d: date, months: int) -> str:
        m = d.month - 1 + months
        y = d.year + m // 12
        return f"{y}-{(m % 12) + 1:02d}"

    def simulate(order, apply_extra):
        bals = {d["id"]: d["balance"] for d in order}
        aprs = {d["id"]: d["apr"] for d in order}
        pays = {d["id"]: d["min_payment"] for d in order}
        total_interest = 0.0
        months = 0
        per_debt_interest: dict[int, float] = {d["id"]: 0.0 for d in order}
        per_debt_months: dict[int, int | None] = {d["id"]: None for d in order}
        remaining = {d["id"] for d in order}
        while remaining and months < _MAX_MONTHS:
            months += 1
            # interest first
            for did in list(remaining):
                i = bals[did] * aprs[did] / 100.0 / 12.0
                bals[did] += i
                total_interest += i
                per_debt_interest[did] += i
            # payments: minimums on all, then extra to the highest-APR alive debt
            budget = apply_extra and extra or 0.0
            for did in list(remaining):
                pay = min(pays[did], bals[did])
                bals[did] -= pay
            if apply_extra and budget > 0 and remaining:
                target = max(remaining, key=lambda k: aprs[k])
                pay = min(budget, bals[target])
                bals[target] -= pay
            for did in list(remaining):
                if bals[did] <= 0.005:
                    per_debt_months[did] = months
                    remaining.discard(did)
        return {
            "months": months if not remaining else None,
            "debt_free": _month_add(date.today(), months) if not remaining else None,
            "total_interest": round(total_interest, 2),
            "per_debt": per_debt_months,
        }

    baseline = simulate(debts, apply_extra=False)
    avalanche = simulate(debts, apply_extra=True) if extra > 0 else None
    return {
        "extra_payment": extra,
        "baseline": baseline,
        "avalanche": avalanche,
        "interest_saved": (
            round(baseline["total_interest"] - (avalanche["total_interest"] or 0.0), 2)
            if avalanche
            else None
        ),
    }
