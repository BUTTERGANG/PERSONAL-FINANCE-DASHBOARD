"""
Transaction categorization — merchant extraction + rule-based bucketing.

Two problems this solves:

1. **Merchant extraction.** Bank statement descriptions bury the real merchant in
   noise: transaction-type prefixes ("Recurring Card Purchase 12/24 …"), reference
   ids ("P928300BAEHM64GFV …"), payment-processor wrappers ("Klarna*Ebay",
   "Sq *Goodfellas"), and trailing location/card tails ("… CA Card 0060").
   `extract_merchant` peels all of that off to a clean brand string. (The old
   `subscriptions._merchant_key` cut at the first digit, collapsing every card
   purchase to "card purchase" and every PayPal row to "p" — this replaces it.)

2. **Categorization.** `auto_categorize` assigns a category using, in order:
   broad/system rules matched on the raw description (payments, transfers, interest,
   ATM, income — which must never count as spend), then learned merchant→category
   rules, then a small built-in seed map of common merchants. Anything unmatched
   stays uncategorized rather than being guessed wildly.
"""

import re
from typing import Optional, Dict


# ── Taxonomy ───────────────────────────────────────────────────────────────────
# Six spend categories (already in the data from Plaid) + broad "system" buckets
# for the non-spend rows that pollute budgets if lumped into spending.
SPEND_CATEGORIES = [
    "Entertainment",
    "Food and Drink",
    "Groceries",
    "Health and Fitness",
    "Shopping",
    "Travel",
]
SYSTEM_CATEGORIES = [
    "Income",
    "Transfer",
    "Payment",
    "Fees & Interest",
    "Cash & ATM",
    "Subscriptions",
    "Other",
]
CATEGORIES = SPEND_CATEGORIES + SYSTEM_CATEGORIES


# ── Merchant extraction ────────────────────────────────────────────────────────

# Payment processors / gateways: the brand comes AFTER the "*". "Sq *Goodfellas" is
# a Square merchant named Goodfellas, not "Square".
_PROCESSOR_PREFIXES = {
    "sq", "tst", "wl", "klarna", "paypal", "pp", "pypl", "sp", "ec",
}
# Brands where the name comes BEFORE the "*": "Google *Workspace" is Google.
_BRAND_STAR = {"google", "amazon", "amzn", "audible", "microsoft", "msft", "apple"}

_LEADING_REF = re.compile(r"^[A-Z0-9]{10,}\s+")  # PayPal/Venmo reference ids
_TYPE_PREFIX = re.compile(
    r"^(?:recurring\s+)?(?:card\s+purchase(?:\s+with\s+pin)?|purchase|pos|pos\s+debit|"
    r"debit\s+card\s+purchase|standard|recurring)\b[\s:]*",
    re.I,
)
_LEADING_DATE = re.compile(r"^\d{1,2}/\d{1,2}(?:/\d{2,4})?\s+")
_STAR_SPLIT = re.compile(r"^([A-Za-z][A-Za-z0-9]*)\s*\*\s*(.+)$")
_TRAIL_CARD = re.compile(r"\s+card\s+\d{3,}.*$", re.I)          # "… CA Card 0060"
_TRAIL_STORE = re.compile(r"\s+#\s*\d+.*$")                      # "… #208 …"
_TRAIL_PHONE = re.compile(r"\s+\d{3}[- ]?\d{3}[- ]?\d{4}.*$")    # support numbers
_TRAIL_DOMAIN = re.compile(r"\s+\S+\.(?:com|io|net|tech|org|co)\b.*$", re.I)
_TRAIL_LONGNUM = re.compile(r"\s+\d{4,}.*$")                     # trailing id runs
_TRAIL_STATE = re.compile(r"\s+[A-Z]{2}\s*$")                    # trailing US state
_MULTISPACE = re.compile(r"\s+")


def extract_merchant(description: str, merchant: Optional[str] = None) -> str:
    """
    Reduce a raw statement description to a clean merchant/brand string.

    If the source already carries a structured `merchant` (Plaid), trust it.
    Otherwise peel prefixes, unwrap processor wrappers, and strip trailing noise.
    Returns "" only when nothing recognizable remains.
    """
    if merchant and merchant.strip():
        return _MULTISPACE.sub(" ", merchant.strip())

    s = (description or "").strip()
    if not s:
        return ""

    # 1. leading reference/id token (PayPal "P928300…", Venmo "7400899…")
    s = _LEADING_REF.sub("", s)
    # 2. transaction-type prefix, then an optional leading MM/DD it wrapped
    s = _TYPE_PREFIX.sub("", s)
    s = _LEADING_DATE.sub("", s)
    s = _TYPE_PREFIX.sub("", s)  # e.g. "Card Purchase 12/24 Recurring …" leftovers

    # 3. processor / brand "*" wrapper
    m = _STAR_SPLIT.match(s)
    if m:
        head, tail = m.group(1), m.group(2)
        s = head if head.lower() in _BRAND_STAR else tail

    # 4. trailing noise (order matters: specific → general)
    s = _TRAIL_CARD.sub("", s)
    s = _TRAIL_DOMAIN.sub("", s)
    s = _TRAIL_STORE.sub("", s)
    s = _TRAIL_PHONE.sub("", s)
    s = _TRAIL_LONGNUM.sub("", s)
    s = _TRAIL_STATE.sub("", s)  # bare trailing US state ("… IN", "… OH")

    s = _MULTISPACE.sub(" ", s).strip(" .,-*")
    return s


def merchant_key(description: str, merchant: Optional[str] = None) -> str:
    """Stable lowercase grouping key derived from the extracted merchant."""
    return extract_merchant(description, merchant).lower()


# ── Broad / system-bucket rules (matched on the raw description) ────────────────
# Each entry: (compiled pattern, category, requires_income_sign). When
# requires_income_sign is True the rule only fires for money-in rows (amount < 0),
# so "payment" from a payroll deposit isn't confused with a card payment.
_SYSTEM_RULES = [
    (re.compile(r"\b(payroll|direct dep|direct deposit)\b", re.I), "Income", False),
    (re.compile(r"\bremote (online )?deposit\b", re.I), "Income", True),
    (re.compile(r"\binterest (charge|charged)\b", re.I), "Fees & Interest", False),
    (re.compile(r"\b(late fee|annual fee|service fee|foreign transaction fee|"
                r"total fees)\b", re.I), "Fees & Interest", False),
    (re.compile(r"\b(online payment|in-app payment|autopay|"
                r"payment,?\s*thank you|epay|e-payment)\b", re.I), "Payment", False),
    (re.compile(r"\b(atm (cash )?(deposit|withdrawal)|cash withdrawal|"
                r"cash deposit)\b", re.I), "Cash & ATM", False),
    (re.compile(r"\b(zelle|venmo|cash app|cashout|real time transfer|"
                r"instant transfer|coinbase|wire transfer|book transfer|"
                r"paypal (inst )?xfer|transfer to|transfer from)\b", re.I),
     "Transfer", False),
]


# ── Built-in merchant seed map (extracted-merchant lowercase → category) ─────────
# Small, high-confidence starter set for common merchants. Learned rules and the
# user's own corrections always take precedence over this.
MERCHANT_SEED: Dict[str, str] = {
    # Groceries
    "fresh thyme": "Groceries", "kroger": "Groceries", "trader joe": "Groceries",
    "whole foods": "Groceries", "aldi": "Groceries", "meijer": "Groceries",
    "costco": "Groceries", "safeway": "Groceries", "publix": "Groceries",
    # Food and Drink
    "chick-fil-a": "Food and Drink", "mcdonald": "Food and Drink",
    "starbucks": "Food and Drink", "chipotle": "Food and Drink",
    "doordash": "Food and Drink", "grubhub": "Food and Drink",
    "taco bell": "Food and Drink", "panera": "Food and Drink",
    "get go": "Food and Drink", "goodfellas": "Food and Drink",
    # Travel
    "uber": "Travel", "lyft": "Travel", "delta": "Travel", "united": "Travel",
    "american air": "Travel", "southwest": "Travel", "marriott": "Travel",
    "airbnb": "Travel", "expedia": "Travel", "shell": "Travel", "bp": "Travel",
    "exxon": "Travel", "chevron": "Travel", "kroger fuel": "Travel",
    # Shopping
    "amazon": "Shopping", "amzn": "Shopping", "ebay": "Shopping",
    "target": "Shopping", "walmart": "Shopping", "best buy": "Shopping",
    "etsy": "Shopping", "pet supplies plus": "Shopping",
    "uncle bills pet": "Shopping", "payless liquors": "Shopping",
    "big red liquors": "Shopping",
    # Entertainment / software / media
    "steam": "Entertainment", "netflix": "Entertainment", "spotify": "Entertainment",
    "hulu": "Entertainment", "disney": "Entertainment", "youtube": "Entertainment",
    "playstation": "Entertainment", "xbox": "Entertainment", "nintendo": "Entertainment",
    # Software / subscriptions (SaaS the user actually has)
    "anthropic": "Subscriptions", "claude.ai": "Subscriptions",
    "claude": "Subscriptions", "replit": "Subscriptions", "google": "Subscriptions",
    "google workspace": "Subscriptions", "workspace": "Subscriptions",
    "honeybook": "Subscriptions", "adobe": "Subscriptions", "dropbox": "Subscriptions",
    "frame.io": "Subscriptions", "frame": "Subscriptions", "neon.tech": "Subscriptions",
    "neon": "Subscriptions", "higgsfield": "Subscriptions", "nvidia": "Subscriptions",
    "motionarray": "Subscriptions", "aura": "Subscriptions", "namecheap": "Subscriptions",
    # Health & fitness
    "usaa insurance": "Health and Fitness", "crew carwash": "Travel",
    "planet fitness": "Health and Fitness", "cvs": "Health and Fitness",
    "walgreens": "Health and Fitness",
}


def auto_categorize(
    description: str,
    amount: float,
    merchant: Optional[str] = None,
    rules: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """
    Choose a category for a transaction, or None to leave it uncategorized.

    Precedence:
      1. broad/system rules on the raw description (income, transfer, payment,
         fees & interest, cash & ATM) — these must win so non-spend rows never
         land in a spend category,
      2. a learned merchant→category rule (exact extracted-merchant match),
      3. the built-in MERCHANT_SEED map (substring match on the extracted merchant).
    """
    desc = description or ""

    # 1. system buckets
    for pattern, category, income_only in _SYSTEM_RULES:
        if pattern.search(desc):
            if income_only and amount >= 0:
                continue
            return category

    key = merchant_key(description, merchant)
    if not key:
        return None

    # 2. learned rules (exact key)
    if rules and key in rules:
        return rules[key]

    # 3. seed map — exact first, then substring (so "uber eats" → Travel via "uber")
    if key in MERCHANT_SEED:
        return MERCHANT_SEED[key]
    for seed_key, category in MERCHANT_SEED.items():
        if seed_key in key:
            return category

    return None
