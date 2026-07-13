"""
Categorization tests — merchant extraction + rule-based bucketing.

Grounded in real descriptions from the statement fixtures so the extractor and the
auto-categorizer are tested against the actual noise banks produce (aggregator
wrappers, reference ids, transaction-type prefixes, location tails).
"""

import pytest

from backend.categorize import extract_merchant, auto_categorize, merchant_key


# ── Merchant extraction ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("description,expected", [
    # Chase card: type-prefix + date + trailing location/card noise
    ("Card Purchase 12/20 Anthropic Anthropic.Com CA Card 0060", "Anthropic"),
    ("Card Purchase With Pin 12/21 Fresh Thyme #208 Indianapolis IN Card 0060", "Fresh Thyme"),
    ("Recurring Card Purchase 12/24 Honeybook, Inc Honeybook.Com CA Card 0060", "Honeybook, Inc"),
    # Aggregator "*" wrappers — processor before the star, merchant after
    ("Card Purchase 12/21 Sq *Goodfellas Broad RI Gosq.Com IN Card 0060", "Goodfellas Broad"),
    ("Card Purchase 12/27 Wl *Steam Purchase 425-9522985 WA Card 0060", "Steam Purchase"),
    ("Card Purchase 12/26 Klarna*Ebay Commerce Columbus OH Card 0060", "Ebay Commerce Columbus"),
    # Brand-first "*" wrapper — keep the brand
    ("Recurring Card Purchase 01/01 Google *Workspace_Wo Cc@Google.Com CA Card 0060", "Google"),
    # PayPal Credit / Venmo: leading reference id + "Standard" prefix
    ("P928300BAEHM64GFV Standard UBER", "UBER"),
    ("P928300QWEHM64GEQ Standard CHICK-FIL-A #01939", "CHICK-FIL-A"),
])
def test_extract_merchant(description, expected):
    assert extract_merchant(description) == expected


def test_extract_merchant_prefers_structured_merchant():
    assert extract_merchant("noisy description 123", merchant="Amazon") == "Amazon"


def test_merchant_key_is_lowercased():
    assert merchant_key("Card Purchase 12/20 Anthropic Anthropic.Com CA Card 0060") == "anthropic"


def test_broken_old_behavior_is_gone():
    # The old _merchant_key collapsed these to "card purchase" / "p". Ensure the real
    # merchant now survives.
    assert extract_merchant("Card Purchase 12/20 Anthropic Anthropic.Com CA Card 0060") != "Card Purchase"
    assert extract_merchant("P928300BAEHM64GFV Standard UBER").lower() != "p"


# ── Broad / system bucketing (these must never count as spend) ──────────────────

@pytest.mark.parametrize("description,amount,expected", [
    ("Complete Wedding Payroll PPD ID: 9111111101", -74.16, "Income"),
    ("Remote Online Deposit 1", -50.00, "Income"),
    ("Venmo Cashout PPD ID: 5264681992", -40.00, "Transfer"),
    ("Zelle Payment From Vicki L Butterfield 27537091732", -100.00, "Transfer"),
    ("Real Time Transfer Recd From Aba/Contr Bnk From: Coinbase", -147.37, "Transfer"),
    ("ATM Cash Deposit 01/11 9820 E 116th St Fishers IN Card 0060", -170.00, "Cash & ATM"),
    ("INTEREST CHARGED TO STANDARD PURCH", 0.08, "Fees & Interest"),
    ("Interest Charge on Purchases", 84.04, "Fees & Interest"),
    ("ONLINE PAYMENT, THANK YOU", -350.00, "Payment"),
    ("IN-APP PAYMENT", -60.00, "Payment"),
])
def test_system_buckets(description, amount, expected):
    assert auto_categorize(description, amount) == expected


# ── Merchant seed categorization ─────────────────────────────────────────────────

@pytest.mark.parametrize("description,amount,expected", [
    ("Card Purchase With Pin 12/21 Fresh Thyme #208 Indianapolis IN Card 0060", 22.98, "Groceries"),
    ("P928300BAEHM64GFV Standard UBER", 9.99, "Travel"),
    ("P928300QWEHM64GEQ Standard CHICK-FIL-A #01939", 35.48, "Food and Drink"),
    ("Card Purchase 12/20 Anthropic Anthropic.Com CA Card 0060", 5.00, "Subscriptions"),
    ("Card Purchase 12/27 Wl *Steam Purchase 425-9522985 WA Card 0060", 12.73, "Entertainment"),
])
def test_seed_categorization(description, amount, expected):
    assert auto_categorize(description, amount) == expected


def test_unknown_merchant_stays_uncategorized():
    # We never guess wildly — an unrecognized local merchant returns None.
    assert auto_categorize("Card Purchase 01/04 Indy Smoke Time Noblesville IN Card 0060", 37.44) is None


def test_learned_rule_takes_precedence_over_seed():
    # A user rule overrides the built-in seed for the same merchant.
    rules = {"anthropic": "Shopping"}
    desc = "Card Purchase 12/20 Anthropic Anthropic.Com CA Card 0060"
    assert auto_categorize(desc, 5.00, rules=rules) == "Shopping"


def test_income_rule_requires_money_in():
    # "Remote Online Deposit" only counts as Income for a money-in (negative) row.
    assert auto_categorize("Remote Online Deposit 1", -50.00) == "Income"
    assert auto_categorize("Remote Online Deposit 1", 50.00) != "Income"
