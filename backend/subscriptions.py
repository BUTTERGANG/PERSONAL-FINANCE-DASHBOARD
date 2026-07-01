"""
Recurring / subscription detection.

Heuristic: group spend transactions by a normalized merchant key, then flag
groups that recur on a regular cadence (weekly … annual) with a consistent
amount. Runs live against the transactions table — no separate storage needed
beyond the user's ignore list.
"""

import re
import statistics
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .models import IgnoredSubscription, Transaction

_UTC = timezone.utc
_LOOKBACK_DAYS = 180
_MIN_OCCURRENCES = 3

# (label, low_days, high_days, occurrences_per_year) — median gap must fall in [low, high].
_FREQUENCIES = [
    ("weekly", 5, 9, 52),
    ("biweekly", 12, 16, 26),
    ("monthly", 26, 35, 12),
    ("quarterly", 85, 95, 4),
    ("annual", 350, 380, 1),
]

_MULTI_SPACE = re.compile(r"\s+")
_NOISE = re.compile(r"[0-9#*].*$")  # drop trailing ids like "AMZN*1A2B3" or store numbers


def _merchant_key(txn: Transaction) -> str:
    """Stable grouping key: prefer the merchant, else the cleaned description."""
    if txn.merchant:
        return txn.merchant.strip().lower()
    desc = (txn.description or "").lower()
    desc = _NOISE.sub("", desc)
    desc = _MULTI_SPACE.sub(" ", desc).strip()
    return desc or (txn.description or "").strip().lower()


def _classify(median_gap: float):
    for label, low, high, per_year in _FREQUENCIES:
        if low <= median_gap <= high:
            return label, per_year
    return None, None


def detect_subscriptions(db: Session) -> list[dict]:
    since = datetime.now(_UTC) - timedelta(days=_LOOKBACK_DAYS)
    txns = (
        db.query(Transaction)
        .filter(Transaction.date >= since, Transaction.amount > 0, Transaction.pending == False)
        .all()
    )

    ignored = {row.merchant_key for row in db.query(IgnoredSubscription).all()}

    groups: dict[str, list[Transaction]] = {}
    for t in txns:
        key = _merchant_key(t)
        if key and key not in ignored:
            groups.setdefault(key, []).append(t)

    results: list[dict] = []
    for key, items in groups.items():
        if len(items) < _MIN_OCCURRENCES:
            continue

        items.sort(key=lambda t: t.date)
        gaps = [(items[i].date - items[i - 1].date).days for i in range(1, len(items))]
        gaps = [g for g in gaps if g > 0]
        if not gaps:
            continue

        median_gap = statistics.median(gaps)
        frequency, per_year = _classify(median_gap)
        if not frequency:
            continue

        amounts = [t.amount for t in items]
        median_amt = statistics.median(amounts)
        if median_amt <= 0:
            continue
        # Reject noisy groups whose amounts swing too much to be a real subscription.
        mean_amt = statistics.mean(amounts)
        cv = (statistics.pstdev(amounts) / mean_amt) if mean_amt else 1.0
        if cv > 0.25:
            continue

        monthly_cost = round(median_amt * per_year / 12, 2)
        last = items[-1]
        results.append(
            {
                "merchant_key": key,
                "merchant": (last.merchant or last.description or key).strip(),
                "category": last.category or "Uncategorized",
                "amount": round(median_amt, 2),
                "frequency": frequency,
                "occurrences": len(items),
                "last_date": last.date.strftime("%Y-%m-%d"),
                "monthly_cost": monthly_cost,
                "est_annual": round(monthly_cost * 12, 2),
            }
        )

    results.sort(key=lambda r: r["monthly_cost"], reverse=True)
    return results
