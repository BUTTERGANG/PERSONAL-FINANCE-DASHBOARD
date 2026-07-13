"""
PDF bank statement parser.

Design: statements differ not just by *bank* but by *product* (Chase checking is
laid out nothing like a Chase credit card). So the unit of tuning is a
``(bank, product)`` **statement type**, each described by a small declarative
config — its sections, the sign of each section, and the printed totals we can
reconcile against.

A section-aware parse:
  1. detect the statement type from header text,
  2. split the statement into its labelled sections,
  3. read transaction lines within each section, applying that section's sign,
  4. reconcile the parsed sums against the statement's own printed totals.

Sign convention (matches manual.py import: "positive = spend", Plaid-style):
  money OUT (purchases, withdrawals, fees) = **positive**
  money IN  (deposits, credits, refunds)   = **negative**

Statement types with a full config today: Chase checking.
Other banks fall back to the legacy line-regex parsers until a real sample
statement is available to build (and test) a proper config.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Callable
import pdfplumber
import fitz  # PyMuPDF


# ──────────────────────────────────────────────────────────────────────────────
# Text extraction (pdfplumber for tables, PyMuPDF for fallback)
# ──────────────────────────────────────────────────────────────────────────────

def extract_text_pdfplumber(pdf_path: str) -> List[str]:
    """Extract text from each page using pdfplumber."""
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return pages_text


def extract_text_pymupdf(pdf_path: str) -> List[str]:
    """Extract text from each page using PyMuPDF (fallback)."""
    pages_text = []
    doc = fitz.open(pdf_path)
    for page in doc:
        text = page.get_text()
        if text:
            pages_text.append(text)
    doc.close()
    return pages_text


def extract_left_column_text(pdf_path: str, x_cutoff: float) -> str:
    """
    Extract text keeping only words whose right edge is left of ``x_cutoff``.

    Multi-column statements (e.g. Citi credit cards) print an unrelated column —
    rewards detail — to the right of the transaction table. Plain text extraction
    interleaves the two, bleeding "...+$0.06" onto every transaction line. Filtering
    by x-coordinate isolates the transaction column so each row reads cleanly:
    ``DATE [POSTDATE] DESCRIPTION AMOUNT``. Words are regrouped into visual lines by
    their vertical (top) position.
    """
    lines_out: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = [w for w in page.extract_words() if w["x1"] <= x_cutoff]
            rows: Dict[int, list] = {}
            for w in words:
                key = round(w["top"] / 3.0)  # bucket words sharing a baseline (~3pt)
                rows.setdefault(key, []).append(w)
            for key in sorted(rows):
                line = " ".join(w["text"] for w in sorted(rows[key], key=lambda w: w["x0"]))
                if line.strip():
                    lines_out.append(line)
    return "\n".join(lines_out)


def extract_all_text(pdf_path: str) -> str:
    """
    Extract all text, trying pdfplumber first then PyMuPDF.

    Pages are joined with a plain newline (no injected page-break marker) so
    that a section spanning a page boundary — e.g. Chase "ELECTRONIC WITHDRAWALS
    (continued)" — reads as one contiguous block.
    """
    pages = extract_text_pdfplumber(pdf_path)
    if not pages:
        pages = extract_text_pymupdf(pdf_path)
    return "\n".join(pages)


# ──────────────────────────────────────────────────────────────────────────────
# Date & amount parsing utilities
# ──────────────────────────────────────────────────────────────────────────────

DATE_PATTERNS = [
    (re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b"), "us"),
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), "iso"),
    (re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),?\s*(\d{4})?\b", re.I), "mon"),
]

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# A trailing money value: 1,234.56  $5.00  (12.00)  -3.18
AMOUNT_RE = re.compile(r"\(?-?\$?\s?[\d,]+\.\d{2}\)?")


def parse_date(date_str: str, year_hint: Optional[int] = None) -> Optional[str]:
    """Parse various date formats to YYYY-MM-DD."""
    date_str = date_str.strip()
    for pattern, fmt in DATE_PATTERNS:
        m = pattern.search(date_str)
        if not m:
            continue
        if fmt == "us":
            mo, day, yr = m.groups()
            if len(yr) == 2:
                yr = "20" + yr
            return f"{int(yr):04d}-{int(mo):02d}-{int(day):02d}"
        elif fmt == "iso":
            yr, mo, day = m.groups()
            return f"{int(yr):04d}-{int(mo):02d}-{int(day):02d}"
        elif fmt == "mon":
            mon_str, day, yr = m.groups()
            mo = MONTH_MAP.get(mon_str[:3].lower())
            if not mo:
                continue
            yr = yr or (str(year_hint) if year_hint else str(datetime.now().year))
            return f"{int(yr):04d}-{mo:02d}-{int(day):02d}"
    return None


def parse_amount(amount_str: str) -> Optional[float]:
    """
    Parse an amount string to a positive magnitude float.

    Sign here is intentionally ignored — section context assigns the final sign
    (see apply). Only the magnitude is returned.
    """
    s = amount_str.strip()
    if not s:
        return None
    s = s.replace("$", "").replace(",", "").replace("(", "").replace(")", "").replace(" ", "").lstrip("-")
    try:
        return abs(float(s))
    except ValueError:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Statement period → year inference
# ──────────────────────────────────────────────────────────────────────────────

# "December 19, 2025 through January 22, 2026" (Chase)
_PERIOD_RE = re.compile(
    r"(\w+\s+\d{1,2},\s*\d{4})\s+(?:through|to|-)\s+(\w+\s+\d{1,2},\s*\d{4})",
    re.I,
)
# "Billing Period: 12/25/25-01/26/26" (Citi) or
# "billing cycle from 01/28/2026 to 02/24/2026" (Venmo/Synchrony)
_PERIOD_NUMERIC_RE = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{2,4})\s*(?:[-–]|to)\s*(\d{1,2}/\d{1,2}/\d{2,4})"
)


@dataclass
class Period:
    start_month: int
    start_year: int
    end_month: int
    end_year: int

    def year_for(self, month: int) -> int:
        """Assign the correct calendar year to a bare MM/DD transaction date."""
        if self.start_year == self.end_year:
            return self.start_year
        # Statement spans a year boundary (e.g. Dec 2025 → Jan 2026):
        # months >= the start month belong to the earlier year.
        return self.start_year if month >= self.start_month else self.end_year


def parse_period(text: str) -> Optional[Period]:
    """
    Extract the statement period. Handles both the Chase long form
    ('December 19, 2025 through January 22, 2026') and the Citi numeric form
    ('Billing Period: 12/25/25-01/26/26').
    """
    m = _PERIOD_RE.search(text)
    if m:
        start, end = parse_date(m.group(1)), parse_date(m.group(2))
    else:
        m = _PERIOD_NUMERIC_RE.search(text)
        start, end = (parse_date(m.group(1)), parse_date(m.group(2))) if m else (None, None)
    if not start or not end:
        return None
    sy, sm, _ = start.split("-")
    ey, em, _ = end.split("-")
    return Period(int(sm), int(sy), int(em), int(ey))


# ──────────────────────────────────────────────────────────────────────────────
# Section-aware statement configs
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Holding:
    """
    One investment position from a brokerage statement (Fidelity). Not a
    transaction — a snapshot of what is owned at statement close.
    """
    description: str
    symbol: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    market_value: Optional[float] = None
    cost_basis: Optional[float] = None       # None when "not applicable" (e.g. money market)
    unrealized_gain: Optional[float] = None

    def as_dict(self) -> Dict:
        return {
            "description": self.description, "symbol": self.symbol,
            "quantity": self.quantity, "price": self.price,
            "market_value": self.market_value, "cost_basis": self.cost_basis,
            "unrealized_gain": self.unrealized_gain,
        }


@dataclass
class SectionSpec:
    """One labelled section of a statement."""
    key: str                 # our internal name, e.g. "deposits"
    sign: int                # +1 = money out (spend), -1 = money in
    # How to locate the section's text. Chase embeds machine markers
    # (*start*name ... *end*name); marker= uses them. Otherwise header/end_headers
    # bound the section by its printed heading text.
    marker: Optional[str] = None
    header: Optional[str] = None
    end_headers: Tuple[str, ...] = ()
    total_label: Optional[str] = None   # printed total line to reconcile against


@dataclass
class SummaryField:
    """
    A headline figure to surface from the statement summary (not a transaction) —
    e.g. the new balance, minimum payment, or credit limit. ``kind`` controls how
    the value is read and typed: 'money' (signed float) or 'date' (YYYY-MM-DD).
    """
    key: str                 # output key, e.g. "new_balance"
    label: str               # printed label to search for
    kind: str = "money"      # "money" | "date"
    account_balance: bool = False  # this field IS the account's current balance


@dataclass
class StatementType:
    bank: str
    product: str
    detect: List[str]                    # regexes; ALL must match (AND) → strong id
    sections: List[SectionSpec]
    # Summary lines for whole-statement reconciliation (optional).
    # For deposit accounts (checking): ending = beginning + net movement.
    # For credit cards (liability): a credit-card summary check is used instead
    # (previous + purchases + interest + fees − payments − credits = new balance).
    beginning_label: Optional[str] = None
    ending_label: Optional[str] = None
    # x_cutoff: keep only words left of this x-coordinate when extracting section
    # text — strips a second column (e.g. Citi rewards) that bleeds into rows.
    # None → use plain full-page text extraction (Chase).
    x_cutoff: Optional[float] = None
    # Credit-card reconciliation: labels of the summary components. When set, the
    # reconciler checks previous + charges − payments == new to the penny.
    cc_summary: Optional[Dict[str, str]] = None
    # activity_anchor: for header-bounded sections, only search for section headers
    # AFTER this string. Statements often repeat a section's name in the summary box
    # (e.g. PayPal's "Payments & Credits $120.00") before the real transaction table;
    # anchoring to "CURRENT ACTIVITY" skips those decoys.
    activity_anchor: Optional[str] = None
    # Headline figures to surface (balances, due dates, limits). Exposed on
    # ParseResult.summary so the importer can display them and update account balance.
    summary: List[SummaryField] = field(default_factory=list)
    # For product="investment": which holdings extractor to use. Fidelity's brokerage
    # ("investment report") and crypto ("client account statement") formats lay out
    # their holdings tables differently, so each names its own parser here.
    holdings_parser: Optional[str] = None   # "fidelity_brokerage" | "fidelity_crypto"

    @property
    def name(self) -> str:
        return f"{self.bank}_{self.product}"


# ── Chase — Total Checking ─────────────────────────────────────────────────────
CHASE_CHECKING = StatementType(
    bank="chase",
    product="checking",
    detect=[r"jpmorgan chase", r"checking summary"],
    sections=[
        SectionSpec("deposits", sign=-1, marker="depositsandadditions",
                    total_label="Total Deposits and Additions"),
        SectionSpec("atm_debit", sign=+1, marker="atmdebitwithdrawal",
                    total_label="Total ATM & Debit Card Withdrawals"),
        SectionSpec("electronic", sign=+1, marker="electronicwithdrawal",
                    total_label="Total Electronic Withdrawals"),
        SectionSpec("fees", sign=+1, marker="fees",
                    total_label="Total Fees"),
    ],
    beginning_label="Beginning Balance",
    ending_label="Ending Balance",
    summary=[
        SummaryField("beginning_balance", "Beginning Balance"),
        SummaryField("ending_balance", "Ending Balance", account_balance=True),
    ],
)

# ── Citi — Costco Anywhere Visa (credit card) ──────────────────────────────────
# Layout differs fundamentally from Chase: no machine markers, a two-column page
# (transactions left, rewards right) that requires x-coordinate filtering, and
# transactions grouped under printed headers. Purchases carry two dates
# (sale + post); we keep the sale date. Credit-card sign convention: purchases,
# interest and fees are spend (+); payments and credits reduce the balance (−).
CITI_CREDIT = StatementType(
    bank="citi",
    product="credit",
    detect=[r"citi", r"costco anywhere visa"],
    x_cutoff=400.0,   # amount column ends ~387; rewards column starts ~415
    sections=[
        SectionSpec("payments", sign=-1,
                    header="Payments, Credits and Adjustments",
                    end_headers=("Standard Purchases", "Fees Charged", "Interest Charged")),
        SectionSpec("purchases", sign=+1,
                    header="Standard Purchases",
                    end_headers=("Fees Charged", "Interest Charged", "TOTAL")),
        SectionSpec("fees", sign=+1,
                    header="Fees Charged",
                    end_headers=("Interest Charged", "TOTAL INTEREST"),
                    total_label="TOTAL FEES FOR THIS PERIOD"),
        SectionSpec("interest", sign=+1,
                    header="Interest Charged",
                    end_headers=("TOTAL INTEREST FOR THIS PERIOD", r"\d{4} totals"),
                    total_label="TOTAL INTEREST FOR THIS PERIOD"),
    ],
    cc_summary={
        "previous": "Previous balance",
        "new": "New balance",
        "payments": "Payments",
        "credits": "Credits",
        "purchases": "Purchases",
        "fees": "Fees",
        "interest": "Interest",
    },
    summary=[
        SummaryField("previous_balance", "Previous balance"),
        # New balance is the card's current balance (a liability). account_balance
        # → the importer can offer to update the Citi account's balance on import.
        SummaryField("new_balance", "New balance", account_balance=True),
        SummaryField("minimum_payment_due", "Minimum payment due"),
        SummaryField("payment_due_date", "Payment due date", kind="date"),
        SummaryField("credit_limit", "Credit Limit"),
        SummaryField("available_credit", "Available Credit Limit"),
    ],
)

# ── PayPal Credit / Synchrony Bank (credit card) ───────────────────────────────
# The cleanest layout of the three credit cards: single column (no x_cutoff needed),
# transactions carry an explicit MM/DD/YY year, and amounts print their own sign
# (payments -$120.00, purchases $9.99). Sections are header-bounded and each closes
# with a "Total ..." line. Summary labels differ from Citi ("INTEREST CHARGES",
# "Available Credit" without "Limit").
PAYPAL_CREDIT = StatementType(
    bank="paypal",
    product="credit",
    detect=[r"paypal credit", r"account summary"],
    activity_anchor="CURRENT ACTIVITY",   # skip the summary box's decoy section names
    sections=[
        SectionSpec("payments", sign=-1,
                    header="PAYMENTS & CREDITS",
                    end_headers=("PURCHASES & ADJUSTMENTS", "INTEREST CHARGED", "FEES"),
                    total_label="Total Payments & Credits"),
        SectionSpec("purchases", sign=+1,
                    header="PURCHASES & ADJUSTMENTS",
                    end_headers=("INTEREST CHARGED", "FEES CHARGED", r"\d{4} Totals"),
                    total_label="Total Purchases & Adjustments"),
        SectionSpec("interest", sign=+1,
                    header="INTEREST CHARGED",
                    end_headers=(r"\d{4} Totals", "NOTICE"),
                    total_label="Total Interest"),
    ],
    cc_summary={
        "previous": "Previous Balance",
        "new": "New Balance",
        "payments": "Payments & Credits",
        "purchases": "Purchases & Adjustments",
        "fees": "Fees",
        "interest": "INTEREST CHARGES",
    },
    summary=[
        SummaryField("previous_balance", "Previous Balance"),
        SummaryField("new_balance", "New Balance", account_balance=True),
        SummaryField("minimum_payment_due", "Minimum Payment Due"),
        SummaryField("payment_due_date", "Payment Due Date", kind="date"),
        SummaryField("credit_limit", "Credit Limit"),
        SummaryField("available_credit", "Available Credit"),
    ],
)

# ── Fidelity — Investment Report (brokerage / IRA) ─────────────────────────────
# Fundamentally different: an investment report, NOT a transaction ledger. It has
# no purchases/payments to import — its meaningful data is the account value and
# the holdings (positions). Internal activity (money-market buys, dividend
# reinvestments) is deliberately NOT imported as transactions — that is not spending
# and would pollute budgets. product="investment" routes parse_statement down the
# holdings path (no sections). Holdings are parsed by _extract_fidelity_holdings and
# reconciled against the account value (sum of market values == account value).
FIDELITY_INVESTMENT = StatementType(
    bank="fidelity",
    product="investment",
    detect=[r"fidelity", r"investment report"],
    sections=[],                       # no transaction sections
    holdings_parser="fidelity_brokerage",
    summary=[
        SummaryField("account_value", "Your Account Value", account_balance=True),
        SummaryField("beginning_value", "Beginning Account Value"),
        SummaryField("ending_value", "Ending Account Value"),
        SummaryField("change_from_last_period", "Change from Last Period"),
        SummaryField("additions", "Additions"),
    ],
)

# ── Fidelity — Crypto (Client Account Statement) ───────────────────────────────
# The user receives a *separate* crypto statement each month alongside the regular
# brokerage one. Different format: header "Client Account Statement" (not "INVESTMENT
# REPORT"), and a cleaner single-line Account Holdings table with an explicit Symbol
# column: "Bitcoin BTC $159.38 0.00235744 $76,566.88 $180.50 $200.00 -$19.50".
# "Your Portfolio Value" has a two-column bleed, so the account balance is taken from
# the clean "Ending Account Value" line instead.
FIDELITY_CRYPTO = StatementType(
    bank="fidelity",
    product="crypto",
    detect=[r"fidelity", r"client account statement", r"crypto"],
    sections=[],
    holdings_parser="fidelity_crypto",
    summary=[
        SummaryField("account_value", "Ending Account Value", account_balance=True),
        SummaryField("beginning_value", "Beginning Account Value"),
        SummaryField("ending_value", "Ending Account Value"),
        SummaryField("change_in_account_value", "Change in Account Value"),
        SummaryField("additions", "Additions"),
    ],
)

# ── Venmo Credit Card / Synchrony Bank (credit card) ───────────────────────────
# Also Synchrony-issued (like PayPal) but a distinct layout. Single column.
# "Transaction details" table; the Payments section header carries its own total on
# the same line ("Payments -$60.00"), and interest-charge rows follow the
# "Total interest charged this period" line (no separate "Interest" header). Balances
# print an "as of MM/DD/YYYY" clause between label and amount ("Previous balance as
# of 01/28/2026 $1,652.85") — handled by the _AS_OF fragment in the summary readers.
VENMO_CREDIT = StatementType(
    bank="venmo",
    product="credit",
    detect=[r"venmo", r"account summary"],
    activity_anchor="Transaction details",
    sections=[
        SectionSpec("payments", sign=-1,
                    header="Payments",
                    end_headers=("Total fees charged this period",
                                 "Total interest charged this period")),
        SectionSpec("interest", sign=+1,
                    header="Total interest charged this period",
                    end_headers=(r"\d{4} Year-to-date", "Interest charge calculation"),
                    total_label="Total interest charged this period"),
    ],
    cc_summary={
        "previous": "Previous balance",
        "new": "New balance",
        "payments": "Payments",
        "fees": "Fees charged",
        "interest": "Interest charges",
    },
    summary=[
        SummaryField("previous_balance", "Previous balance"),
        SummaryField("new_balance", "New balance", account_balance=True),
        SummaryField("minimum_payment_due", "Minimum payment due"),
        SummaryField("payment_due_date", "Payment due date", kind="date"),
        SummaryField("credit_limit", "Credit limit"),
        SummaryField("available_credit", "Available credit"),
    ],
)

# Registry of fully-configured statement types. Detection returns the FIRST match,
# so order matters where detect patterns could overlap: Fidelity crypto is listed
# before Fidelity brokerage because its detect set is a strict superset (crypto
# statements should never fall through to the brokerage holdings parser).
STATEMENT_TYPES: List[StatementType] = [
    CHASE_CHECKING,
    CITI_CREDIT,
    PAYPAL_CREDIT,
    VENMO_CREDIT,
    FIDELITY_CRYPTO,
    FIDELITY_INVESTMENT,
]


# ──────────────────────────────────────────────────────────────────────────────
# Legacy bank detection (used only for the fallback line-regex parsers)
# ──────────────────────────────────────────────────────────────────────────────

# Order matters: more specific issuers are matched first. Patterns avoid common
# statement words — e.g. bare "chase" would match "Purchases", so Chase requires
# "jpmorgan chase" / "chase.com"; "citi" requires a word boundary and its own
# domain to avoid matching inside other words.
BANK_PATTERNS = {
    "fidelity": [r"fidelity brokerage", r"fidelity investments", r"\bfidelity\b"],
    "venmo": [r"\bvenmo\b"],
    "paypal": [r"paypal credit", r"paypal\.com"],
    "citi": [r"citibank", r"citicards", r"\bciti\b"],
    "bofa": [r"bank of america"],
    "wells": [r"wells fargo", r"wellsfargo"],
    "discover": [r"discover\s+(?:card|financial|it)", r"discover\.com"],
    "amex": [r"american express", r"\bamex\b"],
    "capitalone": [r"capital one", r"capitalone"],
    "usbank": [r"u\.?s\.? bank", r"usbank", r"u\.?s\.? bancorp"],
    "chase": [r"jpmorgan chase", r"chase\.com"],
}


def detect_bank(text: str) -> Optional[str]:
    """Detect bank from statement text (legacy fallback path)."""
    text_lower = text.lower()
    for bank, patterns in BANK_PATTERNS.items():
        if any(re.search(p, text_lower) for p in patterns):
            return bank
    return None


def detect_statement_type(text: str) -> Optional[StatementType]:
    """Detect the (bank, product) statement type by matching ALL of its signals."""
    text_lower = text.lower()
    for st in STATEMENT_TYPES:
        if all(re.search(p, text_lower) for p in st.detect):
            return st
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Section extraction & sectioned parsing
# ──────────────────────────────────────────────────────────────────────────────

def _section_text(full_text: str, spec: SectionSpec, activity_anchor: Optional[str] = None) -> str:
    """Return the concatenated text belonging to a section (may repeat across pages)."""
    if spec.marker:
        blocks = re.findall(
            rf"\*start\*{re.escape(spec.marker)}(.*?)\*end\*{re.escape(spec.marker)}",
            full_text, re.S,
        )
        return "\n".join(blocks)
    if spec.header:
        # Skip a leading summary region that repeats section names as decoys.
        if activity_anchor:
            idx = full_text.find(activity_anchor)
            if idx != -1:
                full_text = full_text[idx:]
        # Header-bounded: from the header line to the next section header (or EOF).
        # end_headers are escaped, except a literal "\d{4}" token is kept as a regex
        # so year-prefixed boundaries (r"\d{4} Totals") match any year, not just 2026.
        stops = "|".join(
            re.escape(h).replace(r"\\d\{4\}", r"\d{4}") for h in spec.end_headers
        ) or r"\Z"
        m = re.search(
            rf"{re.escape(spec.header)}(.*?)(?:{stops}|\Z)",
            full_text, re.S | re.I,
        )
        return m.group(1) if m else ""
    return ""


# A transaction row: a leading date (MM/DD or MM/DD/YY[YY]), an optional second
# date (post/tran date, as on Citi and PayPal), the description, then a trailing
# amount. Only the first date is kept; its year is used when present, else the
# statement period infers it. A leading "minus" (PyMuPDF renders "−" as the word
# "minus") or parentheses/"-" on the amount marks it negative in the raw text.
_TXN_LINE_RE = re.compile(
    r"^\s*(\d{1,2}/\d{1,2}(?:/\d{2,4})?)(?:\s+\d{1,2}/\d{1,2}(?:/\d{2,4})?)?\s+(.*\S)\s+"
    r"(minus\s?)?(\(?[-+]?\$?[\d,]+\.\d{2}\)?)\s*$",
    re.I,
)


def _parse_section_lines(
    section_text: str, sign: int, period: Optional[Period]
) -> List[Dict]:
    """Extract transactions from one section, applying the section's sign."""
    year_hint = period.start_year if period else None
    txns: List[Dict] = []
    for raw in section_text.split("\n"):
        line = raw.strip()
        if not line or line.lower().startswith("total"):
            continue
        m = _TXN_LINE_RE.match(line)
        if not m:
            continue  # header rows, continuation/detail lines, blanks
        date_str, desc, minus_word, amount_str = m.groups()
        parts = date_str.split("/")
        try:
            mo, day = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            continue
        if len(parts) == 3:                        # explicit year on the line (Citi, PayPal)
            yr = int(parts[2])
            if yr < 100:
                yr += 2000
        elif period:                               # bare MM/DD → infer from statement period (Chase)
            yr = period.year_for(mo)
        else:
            yr = year_hint or datetime.now().year
        date = f"{yr:04d}-{mo:02d}-{day:02d}"
        mag = parse_amount(amount_str)
        if not mag:                       # skip unparseable and $0.00 rows (e.g. an
            continue                       # unused "INTEREST CHARGE ON CASH ADVANCES $0.00")
        txns.append({
            "date": date,
            "amount": round(sign * mag, 2),
            "description": re.sub(r"\s{2,}", " ", desc).strip(),
        })
    return txns


def _printed_total(full_text: str, label: str) -> Optional[float]:
    """Read a printed total line, e.g. 'Total Electronic Withdrawals $1,071.23'."""
    m = re.search(rf"{re.escape(label)}\s+(\(?-?\$?[\d,]+\.\d{{2}}\)?)", full_text, re.I)
    return parse_amount(m.group(1)) if m else None


def _printed_balance(full_text: str, label: str) -> Optional[float]:
    """Read a signed balance line, e.g. 'Beginning Balance $784.39'."""
    m = re.search(rf"{re.escape(label)}\s+(-?\$?[\d,]+\.\d{{2}})", full_text, re.I)
    if not m:
        return None
    s = m.group(1).replace("$", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Reconciliation
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Reconciliation:
    ok: bool
    sections: Dict[str, Dict] = field(default_factory=dict)  # key -> {parsed, printed, match}
    balance_ok: Optional[bool] = None
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict:
        return {
            "ok": self.ok,
            "sections": self.sections,
            "balance_ok": self.balance_ok,
            "notes": self.notes,
        }


def _reconcile(
    full_text: str,
    st: StatementType,
    per_section: Dict[str, List[Dict]],
) -> Reconciliation:
    """Compare parsed sums to the statement's own printed totals."""
    sections: Dict[str, Dict] = {}
    all_ok = True
    warnings: List[str] = []
    for spec in st.sections:
        rows = per_section.get(spec.key, [])
        if not spec.total_label:
            continue
        printed = _printed_total(full_text, spec.total_label)
        if printed is None:
            # No printed total located. Legitimately-absent sections (e.g. no fees
            # this month) yield 0 rows AND no total — fine. But 0 rows with a total
            # label that should exist may mean the section header drifted and the
            # rows were silently missed, so flag it rather than silently passing.
            if not rows:
                warnings.append(
                    f"Section '{spec.key}' produced no rows and no printed total was "
                    f"found ('{spec.total_label}') — header may have changed."
                )
            continue
        parsed_sum = round(sum(abs(r["amount"]) for r in rows), 2)
        match = abs(parsed_sum - printed) < 0.01
        all_ok = all_ok and match
        sections[spec.key] = {
            "parsed": parsed_sum, "printed": printed,
            "count": len(rows), "match": match,
        }

    recon = Reconciliation(ok=all_ok, sections=sections, notes=warnings)

    # Deposit-account check: beginning + net movement == ending.
    if st.beginning_label and st.ending_label:
        beg = _printed_balance(full_text, st.beginning_label)
        end = _printed_balance(full_text, st.ending_label)
        if beg is not None and end is not None:
            # our amounts are +spend/-income; balance change = income - spend
            net = round(sum(-r["amount"] for rows in per_section.values() for r in rows), 2)
            recon.balance_ok = abs(round(beg + net, 2) - end) < 0.01
            if not recon.balance_ok:
                recon.ok = False
                recon.notes.append(
                    f"Balance check failed: {beg} + ({net}) = {round(beg+net,2)} ≠ {end}"
                )

    # Credit-card check: previous + purchases + interest + fees − payments − credits == new.
    if st.cc_summary:
        _reconcile_credit_card(full_text, st, per_section, recon)

    return recon


def _reconcile_credit_card(
    full_text: str, st: StatementType, per_section: Dict[str, List[Dict]], recon: Reconciliation
) -> None:
    """
    Credit-card balance identity, checked two ways:
      1. printed summary components add up to the printed new balance, and
      2. parsed transaction sums match those printed summary components.
    A credit-card balance is a liability: purchases raise it, payments lower it.
    """
    s = st.cc_summary
    prev = _signed_summary(full_text, s["previous"])
    new = _signed_summary(full_text, s["new"])
    charges = {k: _signed_summary(full_text, s[k]) for k in ("payments", "credits", "purchases", "fees", "interest") if k in s}
    if prev is None or new is None or any(v is None for v in charges.values()):
        return

    # Balance movement by component ROLE, not by the printed sign — issuers are
    # inconsistent about where the minus goes (Citi glues it to the amount,
    # "-$350.00"; PayPal prints it before the label, "- Payments & Credits").
    # A card balance is a liability: payments & credits reduce it; purchases,
    # fees & interest raise it. We take each component's magnitude and apply the
    # role sign ourselves.
    role_sign = {"payments": -1, "credits": -1, "purchases": +1, "fees": +1, "interest": +1}
    movement = round(sum(role_sign[k] * abs(v) for k, v in charges.items()), 2)
    printed_ok = abs(round(prev + movement, 2) - new) < 0.01
    recon.balance_ok = printed_ok
    if not printed_ok:
        recon.ok = False
        recon.notes.append(
            f"CC summary check failed: {prev} + ({movement}) = {round(prev+movement,2)} ≠ {new}"
        )

    # Cross-check parsed transactions against the printed summary components.
    # Map our section keys to summary component magnitudes.
    parsed_by_key = {k: round(sum(abs(r["amount"]) for r in rows), 2) for k, rows in per_section.items()}
    for key in ("payments", "purchases", "fees", "interest"):
        if key not in parsed_by_key or key not in s:
            continue
        printed_mag = abs(charges[key]) if key in charges else None
        if printed_mag is None:
            continue
        match = abs(parsed_by_key[key] - printed_mag) < 0.01
        recon.sections[key] = {
            "parsed": parsed_by_key[key], "printed": printed_mag,
            "count": len(per_section[key]), "match": match,
        }
        if not match:
            recon.ok = False


# Optional "as of MM/DD/YYYY" clause some issuers place between a balance label and
# its amount, e.g. Venmo/Synchrony "Previous balance as of 01/28/2026 $1,652.85".
_AS_OF = r"(?:\s+as of\s+\d{1,2}/\d{1,2}/\d{2,4})?"


def _signed_summary(full_text: str, label: str) -> Optional[float]:
    """
    Read a signed summary amount that may render several ways:
      '+$6.41'  '-$350.00'  'minus$350.00'  '$13,406.59'
      'Previous balance as of 01/28/2026 $1,652.85'
    Returns a signed float (minus/parentheses/'-' → negative).
    """
    m = re.search(
        rf"{re.escape(label)}{_AS_OF}\s*\+?\s*(minus)?\s*(\(?-?\$?[\d,]+\.\d{{2}}\)?)",
        full_text, re.I,
    )
    if not m:
        return None
    neg = bool(m.group(1)) or "(" in m.group(2) or m.group(2).lstrip().startswith("-")
    mag = parse_amount(m.group(2))
    if mag is None:
        return None
    return -mag if neg else mag


# ──────────────────────────────────────────────────────────────────────────────
# Summary-field extraction (headline figures: balances, due dates, limits)
# ──────────────────────────────────────────────────────────────────────────────

# Money that may lack cents ($14,000) or carry a sign; allows the label and value
# to be separated by a newline (two-column layouts put them on adjacent lines) or by
# an "as of DATE" clause (Synchrony balances). Built by concatenation (not .format)
# because _AS_OF contains regex quantifiers like {1,2} that would break str.format.
_SUMMARY_MONEY_TAIL = _AS_OF + r"[:\s]*\+?\s*(minus\s?)?(\(?-?\$?[\d,]+(?:\.\d{2})?\)?)"
_SUMMARY_DATE_TAIL = r"[:\s]*(\d{1,2}/\d{1,2}/\d{2,4})"


def _read_money_field(text: str, label: str) -> Optional[float]:
    m = re.search(re.escape(label) + _SUMMARY_MONEY_TAIL, text, re.I)
    if not m:
        return None
    raw = m.group(2)
    neg = bool(m.group(1)) or "(" in raw or raw.lstrip().startswith("-")
    mag = parse_amount(raw)
    if mag is None:
        return None
    return round(-mag if neg else mag, 2)


def _read_date_field(text: str, label: str) -> Optional[str]:
    m = re.search(re.escape(label) + _SUMMARY_DATE_TAIL, text, re.I)
    return parse_date(m.group(1)) if m else None


def _extract_summary(
    st: StatementType, full_text: str, pymupdf_text: str
) -> Dict[str, object]:
    """
    Read a statement type's headline figures. Tries pdfplumber text first, then
    PyMuPDF text (which preserves reading order where pdfplumber scrambles a
    two-column header — e.g. Citi's Credit Limit / Available Credit).
    """
    out: Dict[str, object] = {}
    for spec in st.summary:
        if spec.kind == "date":
            val = _read_date_field(full_text, spec.label) or _read_date_field(pymupdf_text, spec.label)
        else:
            val = _read_money_field(full_text, spec.label)
            if val is None:
                val = _read_money_field(pymupdf_text, spec.label)
        if val is not None:
            out[spec.key] = val
    return out


def summary_account_balance(st: StatementType, summary: Dict[str, object]) -> Optional[float]:
    """Return the value of the field flagged account_balance, if present."""
    for spec in st.summary:
        if spec.account_balance and spec.key in summary:
            return summary[spec.key]  # type: ignore[return-value]
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Investment holdings extraction (Fidelity)
# ──────────────────────────────────────────────────────────────────────────────

# A holding's data row in the detailed Holdings table, e.g.:
#   FIDELITY GOVERNMENT MONEY $472.85 574.280 $1.0000 $574.28 not applicable not applicable $21.31
#   INVESCO DB MULTI-SECTOR COMMOD $470.00 20.000 $24.8600 $497.20 $420.98 $76.22 $17.92
# Columns after the name: beginning_mv, quantity, price, ending_mv, cost, unrealized, EAI.
# cost/unrealized may be the literal "not applicable" (money-market positions).
_FID_NUM = r"(?:\$?[\d,]+\.\d+|not applicable)"
_FID_HOLDING_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 .,&/-]+?)\s+"
    r"\$?(?P<beginning>[\d,]+\.\d{2})\s+"
    r"(?P<qty>[\d,]+\.\d+)\s+"
    r"\$(?P<price>[\d,]+\.\d+)\s+"
    r"\$?(?P<ending>[\d,]+\.\d{2})\s+"
    rf"(?P<cost>{_FID_NUM})\s+(?P<unrealized>{_FID_NUM})\s+"
    r"\$?[\d,]+\.\d{2}\s*$"     # trailing EAI ($) column
)
# Symbol lives in a parenthetical on the row's continuation line: "MARKET (SPAXX) 3.710%".
_FID_SYMBOL_RE = re.compile(r"\(([A-Z]{2,6})\)")


def _fid_money(s: str) -> Optional[float]:
    """Parse a holdings-table cell to float; 'not applicable' → None."""
    if not s or s.lower().startswith("not applicable"):
        return None
    return parse_amount(s)


def _extract_fidelity_holdings(full_text: str) -> List[Holding]:
    """
    Parse the detailed 'Holdings' table into positions. Each holding spans two
    lines: a data row (name + numeric columns) and a continuation line carrying
    the ticker symbol in parentheses. Rows are scoped to the Holdings section so
    the Estimated-Cash-Flow and disclosure tables aren't mistaken for positions.
    """
    start = full_text.find("Holdings")
    end = full_text.find("Total Holdings")
    region = full_text[start:end] if (start != -1 and end != -1) else full_text

    lines = region.split("\n")
    holdings: List[Holding] = []
    for i, raw in enumerate(lines):
        line = raw.strip()
        if line.lower().startswith("total"):
            continue
        m = _FID_HOLDING_RE.match(line)
        if not m:
            continue
        # The security name wraps onto the continuation line, which also carries the
        # ticker: "MARKET (SPAXX) 3.710%" / "BASE METALS FD (DBB) 3.600%". Stitch the
        # pre-parenthetical text back onto the name, and read the symbol from it.
        name = re.sub(r"\s{2,}", " ", m.group("name")).strip()
        sym_m = _FID_SYMBOL_RE.search(line)
        if not sym_m and i + 1 < len(lines):
            cont = lines[i + 1].strip()
            sym_m = _FID_SYMBOL_RE.search(cont)
            if sym_m:
                tail = cont[:sym_m.start()].strip()
                if tail:
                    name = f"{name} {tail}"
        holdings.append(Holding(
            description=name,
            symbol=sym_m.group(1) if sym_m else None,
            quantity=parse_amount(m.group("qty")),
            price=parse_amount(m.group("price")),
            market_value=parse_amount(m.group("ending")),
            cost_basis=_fid_money(m.group("cost")),
            unrealized_gain=_fid_money(m.group("unrealized")),
        ))
    return holdings


# Fidelity crypto "Account Holdings" rows are single-line with an explicit Symbol
# column and a cleaner layout, e.g.:
#   US Dollar USD $0.00 0.00 $1.00 $0.00 Not Applicable Not Applicable
#   Bitcoin BTC $159.38 0.00235744 $76,566.88 $180.50 $200.00 -$19.50
# Columns: name, symbol, beginning_mv, quantity, price, ending_mv, cost, unrealized.
_FID_CRYPTO_CELL = r"(?:Not Applicable|-?\$[\d,]+\.\d{2})"
_FID_CRYPTO_HOLDING_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z .&/-]+?)\s+(?P<sym>[A-Z]{2,6})\s+"
    r"\$(?P<beginning>[\d,]+\.\d{2})\s+(?P<qty>[\d.]+)\s+\$(?P<price>[\d,]+\.\d+)\s+"
    r"\$(?P<ending>[\d,]+\.\d{2})\s+"
    rf"(?P<cost>{_FID_CRYPTO_CELL})\s+(?P<unrealized>{_FID_CRYPTO_CELL})\s*$"
)


def _extract_fidelity_crypto_holdings(full_text: str) -> List[Holding]:
    """
    Parse the crypto 'Account Holdings' table (single-line rows, explicit symbol
    column). Skips zero-value positions (e.g. the $0.00 USD cash line) so the
    holdings list reflects only real positions — the reconciliation against the
    account value is unaffected (zero adds nothing).
    """
    start = full_text.find("Account Holdings")
    region = full_text[start:] if start != -1 else full_text
    holdings: List[Holding] = []
    for raw in region.split("\n"):
        m = _FID_CRYPTO_HOLDING_RE.match(raw.strip())
        if not m:
            continue
        market_value = parse_amount(m.group("ending"))
        if not market_value:            # drop $0.00 positions (e.g. USD cash line)
            continue
        unreal = m.group("unrealized")
        holdings.append(Holding(
            description=re.sub(r"\s{2,}", " ", m.group("name")).strip(),
            symbol=m.group("sym"),
            quantity=parse_amount(m.group("qty")),
            price=parse_amount(m.group("price")),
            market_value=market_value,
            cost_basis=_fid_money(m.group("cost")),
            unrealized_gain=(
                None if unreal.lower().startswith("not applicable")
                else (-1 if unreal.strip().startswith("-") else 1) * parse_amount(unreal)
            ),
        ))
    return holdings


# Dispatch table: statement type's holdings_parser → extractor function.
_HOLDINGS_PARSERS: Dict[str, Callable[[str], List[Holding]]] = {
    "fidelity_brokerage": _extract_fidelity_holdings,
    "fidelity_crypto": _extract_fidelity_crypto_holdings,
}


def _reconcile_holdings(holdings: List[Holding], account_value: Optional[float]) -> Reconciliation:
    """Investment reconciliation: sum of holding market values == account value."""
    parsed_sum = round(sum(h.market_value or 0.0 for h in holdings), 2)
    if account_value is None:
        return Reconciliation(ok=False, notes=["No account value found to reconcile against."])
    match = abs(parsed_sum - account_value) < 0.01
    recon = Reconciliation(
        ok=match,
        sections={"holdings": {
            "parsed": parsed_sum, "printed": round(account_value, 2),
            "count": len(holdings), "match": match,
        }},
        balance_ok=match,
    )
    if not match:
        recon.notes.append(
            f"Holdings sum {parsed_sum} ≠ account value {account_value}"
        )
    return recon


# ──────────────────────────────────────────────────────────────────────────────
# Legacy line-regex parsers (fallback for banks without a section config yet)
# ──────────────────────────────────────────────────────────────────────────────

def _legacy_line_parser(date_re: str) -> Callable[[str], List[Dict]]:
    pat = re.compile(rf"({date_re})\s+(.+?)\s+([\$\-\(\)\d,]+\.\d{{2}})")

    def parse(text: str) -> List[Dict]:
        out = []
        for line in text.split("\n"):
            m = pat.search(line)
            if not m:
                continue
            date_str, desc, amount_str = m.group(1), m.group(2), m.group(3)
            date = parse_date(date_str)
            s = amount_str.strip()
            neg = s.startswith("(") and s.endswith(")")
            mag = parse_amount(s)
            if date and mag is not None:
                out.append({
                    "date": date,
                    "amount": round(-mag if neg else mag, 2),
                    "description": desc.strip(),
                })
        return out

    return parse


_LEGACY = {
    "chase": _legacy_line_parser(r"\d{1,2}/\d{1,2}"),
    "citi": _legacy_line_parser(r"\d{1,2}/\d{1,2}"),
    "bofa": _legacy_line_parser(r"\d{1,2}/\d{1,2}/\d{2,4}"),
    "wells": _legacy_line_parser(r"\d{1,2}/\d{1,2}"),
    "discover": _legacy_line_parser(r"\d{1,2}/\d{1,2}/\d{2,4}"),
    "amex": _legacy_line_parser(r"\d{1,2}/\d{1,2}/\d{2,4}"),
    "capitalone": _legacy_line_parser(r"\d{1,2}/\d{1,2}/\d{2,4}"),
    "usbank": _legacy_line_parser(r"\d{1,2}/\d{1,2}/\d{2,4}"),
}


def parse_generic_tables(pdf_path: str) -> List[Dict]:
    """Extract transactions from tables using pdfplumber (last-resort fallback)."""
    transactions = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table or len(table) < 2:
                    continue
                header_row = None
                for i, row in enumerate(table):
                    if not row:
                        continue
                    row_text = " ".join(str(c).lower() if c else "" for c in row)
                    if any(kw in row_text for kw in ["date", "desc", "amount", "debit", "credit"]):
                        header_row = i
                        break
                if header_row is None:
                    continue
                header = table[header_row]
                date_col = desc_col = amount_col = None
                for j, col in enumerate(header):
                    if not col:
                        continue
                    cl = str(col).lower()
                    if "date" in cl or "posted" in cl:
                        date_col = j
                    elif any(k in cl for k in ("desc", "name", "payee", "memo")):
                        desc_col = j
                    elif any(k in cl for k in ("amount", "debit", "credit")):
                        amount_col = j
                if date_col is None or (desc_col is None and amount_col is None):
                    continue
                for row in table[header_row + 1:]:
                    if not row or len(row) <= max(date_col, desc_col or 0, amount_col or 0):
                        continue
                    date = parse_date(str(row[date_col]) if row[date_col] else "")
                    desc = str(row[desc_col]) if desc_col is not None and row[desc_col] else ""
                    amount = parse_amount(str(row[amount_col]) if amount_col is not None and row[amount_col] else "")
                    if date and amount is not None and desc:
                        transactions.append({"date": date, "amount": amount, "description": desc.strip()})
    return transactions


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ParseResult:
    transactions: List[Dict]
    bank: str
    product: str                       # "checking", "credit", ... or "unknown"
    reconciliation: Optional[Reconciliation] = None
    method: str = "sectioned"          # "sectioned" | "legacy" | "generic_table"
    # Headline figures read from the statement summary (balances, due date, limits).
    summary: Dict[str, object] = field(default_factory=dict)
    # The statement's stated account balance (from the account_balance summary
    # field), if any — the importer can offer to sync this onto the account.
    account_balance: Optional[float] = None
    # Investment positions (Fidelity). Empty for transaction statements.
    holdings: List[Holding] = field(default_factory=list)

    @property
    def statement_type(self) -> str:
        return f"{self.bank}_{self.product}" if self.product != "unknown" else self.bank


def _dedupe(transactions: List[Dict]) -> List[Dict]:
    seen, unique = set(), []
    for t in transactions:
        key = (t["date"], round(t["amount"], 2), t["description"][:50])
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return unique


def parse_statement(pdf_path: str, bank_hint: Optional[str] = None) -> ParseResult:
    """
    Parse a bank statement PDF into a ParseResult (transactions + reconciliation).

    Strategy: section-aware config first (accurate, self-verifying); fall back to
    the legacy line-regex parser, then a generic table parser, for statement types
    without a config yet.
    """
    full_text = extract_all_text(pdf_path)
    # PyMuPDF text preserves reading order where pdfplumber scrambles a two-column
    # header (Citi). Used as a fallback for period detection and summary fields.
    pymupdf_text = "\n".join(extract_text_pymupdf(pdf_path))
    period = parse_period(full_text) or parse_period(pymupdf_text)

    st = detect_statement_type(full_text)
    if st and st.holdings_parser:
        # Investment/crypto statements have no transaction sections — extract holdings
        # + summary and reconcile the holdings sum against the account value. The
        # extractor is chosen per statement type (brokerage vs crypto layouts differ).
        summary = _extract_summary(st, full_text, pymupdf_text)
        account_value = summary_account_balance(st, summary)
        holdings = _HOLDINGS_PARSERS[st.holdings_parser](full_text)
        return ParseResult(
            transactions=[], bank=st.bank, product=st.product,
            reconciliation=_reconcile_holdings(holdings, account_value),
            method="investment", summary=summary,
            account_balance=account_value, holdings=holdings,
        )
    if st:
        # For multi-column statements (x_cutoff set), parse transaction *sections*
        # from the isolated left column so the neighbouring column doesn't bleed in.
        # Reconciliation summary labels are still read from full_text — those totals
        # live in their own summary block, and dropping columns could hide them.
        section_source = (
            extract_left_column_text(pdf_path, st.x_cutoff)
            if st.x_cutoff is not None else full_text
        )
        per_section = {
            spec.key: _parse_section_lines(
                _section_text(section_source, spec, st.activity_anchor), spec.sign, period
            )
            for spec in st.sections
        }
        txns = [t for rows in per_section.values() for t in rows]
        recon = _reconcile(full_text, st, per_section)
        summary = _extract_summary(st, full_text, pymupdf_text)
        return ParseResult(
            transactions=_dedupe(txns), bank=st.bank, product=st.product,
            reconciliation=recon, method="sectioned",
            summary=summary, account_balance=summary_account_balance(st, summary),
        )

    # Fallback: legacy per-bank line regex, then generic tables.
    bank = bank_hint or detect_bank(full_text) or "unknown"
    txns = _LEGACY[bank](full_text) if bank in _LEGACY else []
    method = "legacy"
    if not txns:
        txns = parse_generic_tables(pdf_path)
        method = "generic_table"
    return ParseResult(
        transactions=_dedupe(txns), bank=bank, product="unknown",
        reconciliation=None, method=method,
    )


def parse_pdf_statement(pdf_path: str, bank_hint: Optional[str] = None) -> Tuple[List[Dict], str]:
    """Backward-compatible shim: returns (transactions, bank)."""
    result = parse_statement(pdf_path, bank_hint)
    return result.transactions, result.bank


# ──────────────────────────────────────────────────────────────────────────────
# Preview/debug helper
# ──────────────────────────────────────────────────────────────────────────────

def preview_pdf(pdf_path: str, max_chars: int = 3000) -> Dict:
    """Return preview info for debugging."""
    full_text = extract_all_text(pdf_path)
    result = parse_statement(pdf_path)
    return {
        "bank_detected": result.bank,
        "statement_type": result.statement_type,
        "method": result.method,
        "text_preview": full_text[:max_chars],
        "transaction_count": len(result.transactions),
        "sample_transactions": result.transactions[:5],
        "reconciliation": result.reconciliation.as_dict() if result.reconciliation else None,
    }
