from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Account types treated as debt when computing net worth.
# Shared by the sync layer (snapshots) and API so the math is defined in one place.
CREDIT_TYPES = {"credit"}


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    institution = Column(String, nullable=False)  # chase, citi, fidelity, paypal, venmo
    account_type = Column(String, nullable=False)  # checking, savings, credit, investment
    balance = Column(Float, default=0.0)
    available_balance = Column(Float, nullable=True)
    currency = Column(String, default="USD")
    # Plaid access token encrypted with Fernet before storage
    plaid_access_token_enc = Column(Text, nullable=True)
    plaid_item_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    last_synced = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True)
    account_id = Column(String, nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Float, nullable=False)   # positive = debit/spend, negative = credit/refund
    description = Column(String, nullable=False)
    category = Column(String, nullable=True)
    merchant = Column(String, nullable=True)
    pending = Column(Boolean, default=False)
    source = Column(String, default="plaid")  # plaid | ofx
    created_at = Column(DateTime(timezone=True), default=_now)


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String, nullable=True)
    institution = Column(String, nullable=False)
    status = Column(String, nullable=False)  # success | error
    transactions_added = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    synced_at = Column(DateTime(timezone=True), default=_now)


class IgnoredSubscription(Base):
    """Merchant keys the user dismissed from subscription detection (false positives)."""

    __tablename__ = "ignored_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_key = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)


class CategoryRule(Base):
    """
    A learned merchant→category mapping. Created when the user corrects a
    transaction's category; re-applied to existing rows and future imports so a
    merchant only has to be categorized once.
    """

    __tablename__ = "category_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_key = Column(String, unique=True, nullable=False)
    category = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class Budget(Base):
    """A monthly spending limit for one category."""

    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String, unique=True, nullable=False)
    limit_amount = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class NetWorthSnapshot(Base):
    """One row per calendar day capturing total net worth for the trend chart."""

    __tablename__ = "net_worth_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    day = Column(String, unique=True, nullable=False)  # YYYY-MM-DD (UTC), dedupe key
    captured_at = Column(DateTime(timezone=True), default=_now)
    net_worth = Column(Float, nullable=False)
    total_assets = Column(Float, nullable=False)
    total_debt = Column(Float, nullable=False)
    breakdown_json = Column(Text, nullable=True)  # per-institution balances at capture time
