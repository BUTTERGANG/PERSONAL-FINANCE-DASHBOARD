from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CategoryRule, Transaction
from ..categorize import CATEGORIES, auto_categorize, merchant_key

router = APIRouter()

_UTC = timezone.utc


def load_rules(db: Session) -> dict[str, str]:
    """All learned merchant→category rules as a dict for auto_categorize()."""
    return {r.merchant_key: r.category for r in db.query(CategoryRule).all()}


class TransactionOut(BaseModel):
    id: str
    account_id: str
    date: datetime
    amount: float
    description: str
    category: Optional[str]
    merchant: Optional[str]
    pending: bool
    source: str

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[TransactionOut])
def list_transactions(
    account_id: Optional[str] = None,
    days: int = Query(default=30, ge=1, le=365),
    search: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    since = datetime.now(_UTC) - timedelta(days=days)
    q = db.query(Transaction).filter(Transaction.date >= since)

    if account_id:
        q = q.filter(Transaction.account_id == account_id)
    if category:
        q = q.filter(Transaction.category == category)
    if search:
        q = q.filter(Transaction.description.ilike(f"%{search}%"))

    return q.order_by(Transaction.date.desc()).limit(500).all()


@router.get("/summary")
def spending_summary(days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)):
    since = datetime.now(_UTC) - timedelta(days=days)
    rows = (
        db.query(Transaction.category, func.sum(Transaction.amount).label("total"))
        .filter(Transaction.date >= since, Transaction.amount > 0, Transaction.pending == False)
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )
    return [{"category": r.category or "Uncategorized", "total": round(r.total, 2)} for r in rows]


@router.get("/mom")
def month_over_month(db: Session = Depends(get_db)):
    """
    Compare this calendar month's spending to last month's, by category.
    Last month's total is prorated to the same day-of-month so early-month
    comparisons aren't uselessly lopsided.
    """
    now = datetime.now(_UTC)
    this_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_start = (this_start - timedelta(days=1)).replace(day=1)

    def _spent(start: datetime, end: datetime) -> dict[str, float]:
        rows = (
            db.query(Transaction.category, func.sum(Transaction.amount).label("total"))
            .filter(
                Transaction.date >= start,
                Transaction.date < end,
                Transaction.amount > 0,
                Transaction.pending == False,
            )
            .group_by(Transaction.category)
            .all()
        )
        return {(r.category or "Uncategorized"): float(r.total or 0.0) for r in rows}

    this_month = _spent(this_start, now)
    last_full = _spent(last_start, this_start)
    # Same-day-of-month slice of last month, for a fair pace comparison.
    last_to_date = _spent(last_start, min(last_start + (now - this_start), this_start))

    out = []
    for category in sorted(set(this_month) | set(last_full)):
        cur = round(this_month.get(category, 0.0), 2)
        prev_full = round(last_full.get(category, 0.0), 2)
        prev_pace = round(last_to_date.get(category, 0.0), 2)
        base = prev_pace if prev_pace > 0 else None
        pct_change = round((cur - base) / base * 100, 1) if base else None
        out.append(
            {
                "category": category,
                "this_month": cur,
                "last_month_same_point": prev_pace,
                "last_month_total": prev_full,
                "pct_change": pct_change,  # None = no spend at this point last month
            }
        )

    out.sort(key=lambda r: r["this_month"], reverse=True)
    return {
        "month": this_start.strftime("%Y-%m"),
        "prev_month": last_start.strftime("%Y-%m"),
        "day_of_month": now.day,
        "categories": out,
        "total_this_month": round(sum(r["this_month"] for r in out), 2),
        "total_last_month_same_point": round(sum(r["last_month_same_point"] for r in out), 2),
    }


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    """
    The category taxonomy for dropdowns: the fixed set (6 spend + system buckets)
    unioned with any custom categories already present in the data, in a stable order.
    """
    in_use = {
        r.category
        for r in db.query(Transaction.category).filter(Transaction.category.isnot(None)).distinct()
    }
    extras = sorted(in_use - set(CATEGORIES))
    return CATEGORIES + extras


# ── Categorization ──────────────────────────────────────────────────────────────

class CategoryUpdate(BaseModel):
    category: Optional[str] = None       # None/"" clears the category
    # When true (default), remember this merchant→category and apply it to the
    # merchant's other rows + future imports.
    apply_to_merchant: bool = True


@router.patch("/{txn_id}")
def update_category(txn_id: str, payload: CategoryUpdate, db: Session = Depends(get_db)):
    """
    Set (or clear) a transaction's category. By default this also learns a
    merchant→category rule and re-applies it to the merchant's other rows so the
    same merchant never has to be categorized twice.
    """
    txn = db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    new_category = (payload.category or "").strip() or None
    old_category = txn.category
    txn.category = new_category

    applied = 1
    key = merchant_key(txn.description or "", txn.merchant)

    if payload.apply_to_merchant and key:
        # Upsert / remove the learned rule.
        rule = db.query(CategoryRule).filter(CategoryRule.merchant_key == key).one_or_none()
        if new_category:
            if rule:
                rule.category = new_category
            else:
                db.add(CategoryRule(merchant_key=key, category=new_category))
        elif rule:
            db.delete(rule)

        # Re-apply to the merchant's other rows. To avoid stomping unrelated manual
        # edits, only touch rows that are uncategorized or still hold the old value.
        for other in db.query(Transaction).filter(Transaction.id != txn_id):
            if merchant_key(other.description or "", other.merchant) != key:
                continue
            if other.category in (None, old_category):
                other.category = new_category
                applied += 1

    db.commit()
    return {"status": "updated", "category": new_category, "rows_updated": applied}


@router.post("/auto-categorize")
def run_auto_categorize(only_uncategorized: bool = True, db: Session = Depends(get_db)):
    """
    Apply system buckets + learned rules + the seed map to transactions. By default
    only fills in uncategorized rows; pass only_uncategorized=false to re-run over all.
    Returns how many rows were categorized.
    """
    rules = load_rules(db)
    q = db.query(Transaction)
    if only_uncategorized:
        q = q.filter(Transaction.category.is_(None))

    updated = 0
    for t in q.all():
        cat = auto_categorize(t.description or "", t.amount, t.merchant, rules)
        if cat and cat != t.category:
            t.category = cat
            updated += 1

    db.commit()
    total_uncat = db.query(Transaction).filter(Transaction.category.is_(None)).count()
    return {"status": "done", "categorized": updated, "still_uncategorized": total_uncat}


# ── Learned rules ────────────────────────────────────────────────────────────────

class RuleOut(BaseModel):
    merchant_key: str
    category: str

    model_config = {"from_attributes": True}


@router.get("/rules", response_model=list[RuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.query(CategoryRule).order_by(CategoryRule.merchant_key).all()


@router.delete("/rules/{merchant_key}")
def delete_rule(merchant_key: str, db: Session = Depends(get_db)):
    rule = db.query(CategoryRule).filter(CategoryRule.merchant_key == merchant_key).one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found.")
    db.delete(rule)
    db.commit()
    return {"status": "deleted", "merchant_key": merchant_key}
