"""
Persist investment positions parsed from brokerage statements (Fidelity
brokerage + crypto) and aggregate them into a portfolio view.

Positions are keyed by (account_id, position_key) so re-importing a later
statement refreshes a position in place rather than duplicating it. The
portfolio aggregation computes market value, cost basis and unrealized gain
per account and overall.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from .models import Account, Holding

# Fields copied straight off a parsed Holding (pdf_parser.Holding.as_dict()).
_POSITION_FIELDS = (
    "description",
    "symbol",
    "quantity",
    "price",
    "market_value",
    "cost_basis",
    "unrealized_gain",
)


def position_key(symbol: Optional[str], description: str) -> str:
    """
    Stable identity of a position within an account: the ticker when the
    statement gives one, otherwise a slug of the description (money-market and
    crypto lines often have no symbol).
    """
    if symbol and symbol.strip():
        return symbol.strip().upper()
    slug = re.sub(r"[^a-z0-9]+", "-", (description or "").lower()).strip("-")
    return (slug or "position")[:80]


def upsert_holdings(
    db: Session,
    account_id: str,
    rows: Iterable[dict],
    source: str = "pdf",
    as_of: Optional[str] = None,
) -> dict:
    """
    Insert or refresh positions for one account. `rows` are dicts shaped like
    pdf_parser.Holding.as_dict(). Returns {"added", "updated", "total"}.
    Caller commits.
    """
    added = updated = 0
    for row in rows:
        description = (row.get("description") or "").strip()
        if not description:
            continue
        key = position_key(row.get("symbol"), description)
        existing = (
            db.query(Holding)
            .filter(Holding.account_id == account_id, Holding.position_key == key)
            .first()
        )
        if existing:
            for field in _POSITION_FIELDS:
                # Only overwrite with a real value: a statement that doesn't carry a
                # column (or parses it as blank) must not wipe what we already know.
                value = row.get(field)
                if value is not None:
                    setattr(existing, field, value)
            existing.source = source
            if as_of:
                existing.as_of = as_of
            updated += 1
        else:
            payload = {field: row.get(field) for field in _POSITION_FIELDS}
            payload["description"] = description
            db.add(
                Holding(
                    account_id=account_id,
                    position_key=key,
                    source=source,
                    as_of=as_of,
                    **payload,
                )
            )
            added += 1
    return {"added": added, "updated": updated, "total": added + updated}


def _gain(h: Holding) -> Optional[float]:
    """Unrealized gain: the statement's figure when present, else market − cost."""
    if h.unrealized_gain is not None:
        return h.unrealized_gain
    if h.market_value is not None and h.cost_basis is not None:
        return round(h.market_value - h.cost_basis, 2)
    return None


def _holding_row(h: Holding, account_name: str) -> dict:
    return {
        "id": h.id,
        "account_id": h.account_id,
        "account_name": account_name,
        "symbol": h.symbol,
        "description": h.description,
        "quantity": h.quantity,
        "price": h.price,
        "market_value": h.market_value,
        "cost_basis": h.cost_basis,
        # Effective gain (statement figure, else market − cost) so a row always
        # agrees with the totals that sum the same values.
        "unrealized_gain": _gain(h),
        "as_of": h.as_of,
        "source": h.source,
    }


def portfolio(db: Session) -> dict:
    """
    All holdings grouped by account, with per-account and grand totals
    (market value, cost basis, unrealized gain).
    """
    names = {a.id: a.name for a in db.query(Account).all()}
    holdings = db.query(Holding).all()

    by_account: dict[str, dict] = {}
    for h in holdings:
        account_name = names.get(h.account_id, h.account_id)
        bucket = by_account.setdefault(
            h.account_id,
            {
                "account_id": h.account_id,
                "account_name": account_name,
                "positions": 0,
                "market_value": 0.0,
                "cost_basis": 0.0,
                "unrealized_gain": 0.0,
                "holdings": [],
            },
        )
        bucket["positions"] += 1
        bucket["market_value"] += h.market_value or 0.0
        bucket["cost_basis"] += h.cost_basis or 0.0
        bucket["unrealized_gain"] += _gain(h) or 0.0
        bucket["holdings"].append(_holding_row(h, account_name))

    accounts = []
    totals = {"positions": 0, "market_value": 0.0, "cost_basis": 0.0, "unrealized_gain": 0.0}
    for bucket in by_account.values():
        for key in ("market_value", "cost_basis", "unrealized_gain"):
            bucket[key] = round(bucket[key], 2)
        bucket["holdings"].sort(key=lambda r: (r["market_value"] or 0.0), reverse=True)
        accounts.append(bucket)

    accounts.sort(key=lambda b: b["market_value"], reverse=True)
    for bucket in accounts:
        totals["positions"] += bucket["positions"]
        totals["market_value"] += bucket["market_value"]
        totals["cost_basis"] += bucket["cost_basis"]
        totals["unrealized_gain"] += bucket["unrealized_gain"]
    for key in ("market_value", "cost_basis", "unrealized_gain"):
        totals[key] = round(totals[key], 2)
    totals["return_pct"] = (
        round(totals["unrealized_gain"] / totals["cost_basis"] * 100, 2)
        if totals["cost_basis"]
        else None
    )

    return {"accounts": accounts, "totals": totals}
