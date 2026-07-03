"""
PDF bank statement parser.
Supports: Chase, Citi, Bank of America, Wells Fargo, Discover, Amex, Capital One, US Bank.
Returns normalized transactions: [{date, amount, description, category?}]
"""

import re
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import pdfplumber
import fitz  # PyMuPDF


# ──────────────────────────────────────────────────────────────────────────────
# Bank detection & parsing strategies
# ──────────────────────────────────────────────────────────────────────────────

BANK_PATTERNS = {
    "chase": {
        "detect": [r"chase", r"jpmorgan chase"],
        "parser": "chase",
    },
    "citi": {
        "detect": [r"citibank", r"citi ", r"citi\b"],
        "parser": "citi",
    },
    "bofa": {
        "detect": [r"bank of america", r"boa\b"],
        "parser": "bofa",
    },
    "wells": {
        "detect": [r"wells fargo", r"wellsfargo"],
        "parser": "wells",
    },
    "discover": {
        "detect": [r"discover"],
        "parser": "discover",
    },
    "amex": {
        "detect": [r"american express", r"amex\b"],
        "parser": "amex",
    },
    "capitalone": {
        "detect": [r"capital one", r"capitalone"],
        "parser": "capitalone",
    },
    "usbank": {
        "detect": [r"u\.?s\.? bank", r"usbank", r"u\.?s\.? bancorp"],
        "parser": "usbank",
    },
}


def detect_bank(text: str) -> Optional[str]:
    """Detect bank from first page text."""
    text_lower = text.lower()
    for bank, config in BANK_PATTERNS.items():
        for pattern in config["detect"]:
            if re.search(pattern, text_lower):
                return bank
    return None


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
            # Also extract tables
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if row:
                        pages_text.append(" | ".join(str(c) if c else "" for c in row))
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


def extract_all_text(pdf_path: str) -> str:
    """Extract all text, trying pdfplumber first then PyMuPDF."""
    pages = extract_text_pdfplumber(pdf_path)
    if not pages:
        pages = extract_text_pymupdf(pdf_path)
    return "\n\n=== PAGE BREAK ===\n\n".join(pages)


# ──────────────────────────────────────────────────────────────────────────────
# Date parsing utilities
# ──────────────────────────────────────────────────────────────────────────────

DATE_PATTERNS = [
    # MM/DD/YYYY or MM/DD/YY
    (re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b"), "us"),
    # YYYY-MM-DD
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), "iso"),
    # MMM DD or MMM DD, YYYY
    (re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),?\s*(\d{4})?\b", re.I), "mon"),
]

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


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
            if not yr and year_hint:
                yr = str(year_hint)
            elif not yr:
                yr = str(datetime.now().year)
            return f"{int(yr):04d}-{mo:02d}-{int(day):02d}"

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Amount parsing
# ──────────────────────────────────────────────────────────────────────────────

AMOUNT_PATTERN = re.compile(
    r"""
    (?:
        \(\s*\$?[\d,]+\.?\d*\s*\)      # (123.45) or ($123.45) - negative
        |
        \$\s*[\d,]+\.?\d*              # $123.45
        |
        [\d,]+\.\d{2}                  # 123.45
    )
    """,
    re.VERBOSE,
)


def parse_amount(amount_str: str) -> Optional[float]:
    """Parse amount string to float. Parentheses = negative (spend)."""
    s = amount_str.strip()
    if not s:
        return None

    # Check for parentheses (negative)
    is_negative = s.startswith("(") and s.endswith(")")

    # Clean: remove $, commas, parentheses
    s = s.replace("$", "").replace(",", "").replace("(", "").replace(")", "").strip()

    try:
        val = float(s)
        return -val if is_negative else val
    except ValueError:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Bank-specific parsers
# ──────────────────────────────────────────────────────────────────────────────

def parse_chase(text: str) -> List[Dict]:
    """Parse Chase checking/savings/credit statements."""
    transactions = []

    # Chase format: DATE DESCRIPTION AMOUNT BALANCE
    # Often in table format
    lines = text.split("\n")

    for line in lines:
        # Match: MM/DD  DESCRIPTION  AMOUNT  BALANCE
        m = re.search(
            r"(\d{1,2}/\d{1,2})\s+(.+?)\s+([\$\-\(\)\d,]+\.\d{2})\s+([\$\-\(\)\d,]+\.\d{2})",
            line
        )
        if m:
            date_str, desc, amount_str, _ = m.groups()
            date = parse_date(date_str)
            amount = parse_amount(amount_str)
            if date and amount is not None:
                transactions.append({
                    "date": date,
                    "amount": amount,
                    "description": desc.strip(),
                })

    return transactions


def parse_citi(text: str) -> List[Dict]:
    """Parse Citi credit card statements."""
    transactions = []

    # Citi format varies; try common patterns
    # Pattern: MM/DD/MM/DD DESCRIPTION AMOUNT
    lines = text.split("\n")

    for line in lines:
        # MM/DD/MM/DD  DESCRIPTION  AMOUNT
        m = re.search(
            r"(\d{1,2}/\d{1,2})\s+\d{1,2}/\d{1,2}\s+(.+?)\s+([\$\-\(\)\d,]+\.\d{2})",
            line
        )
        if m:
            date_str, desc, amount_str = m.groups()
            date = parse_date(date_str)
            amount = parse_amount(amount_str)
            if date and amount is not None:
                transactions.append({
                    "date": date,
                    "amount": amount,
                    "description": desc.strip(),
                })

    return transactions


def parse_bofa(text: str) -> List[Dict]:
    """Parse Bank of America statements."""
    transactions = []

    # BoA often: MM/DD/YYYY DESCRIPTION AMOUNT
    lines = text.split("\n")

    for line in lines:
        m = re.search(
            r"(\d{1,2}/\d{1,2}/\d{2,4})\s+(.+?)\s+([\$\-\(\)\d,]+\.\d{2})",
            line
        )
        if m:
            date_str, desc, amount_str = m.groups()
            date = parse_date(date_str)
            amount = parse_amount(amount_str)
            if date and amount is not None:
                transactions.append({
                    "date": date,
                    "amount": amount,
                    "description": desc.strip(),
                })

    return transactions


def parse_wells(text: str) -> List[Dict]:
    """Parse Wells Fargo statements."""
    transactions = []

    lines = text.split("\n")
    for line in lines:
        # MM/DD DESCRIPTION AMOUNT
        m = re.search(
            r"(\d{1,2}/\d{1,2})\s+(.+?)\s+([\$\-\(\)\d,]+\.\d{2})",
            line
        )
        if m:
            date_str, desc, amount_str = m.groups()
            date = parse_date(date_str)
            amount = parse_amount(amount_str)
            if date and amount is not None:
                transactions.append({
                    "date": date,
                    "amount": amount,
                    "description": desc.strip(),
                })

    return transactions


def parse_discover(text: str) -> List[Dict]:
    """Parse Discover card statements."""
    transactions = []

    lines = text.split("\n")
    for line in lines:
        # MM/DD/YYYY DESCRIPTION AMOUNT
        m = re.search(
            r"(\d{1,2}/\d{1,2}/\d{2,4})\s+(.+?)\s+([\$\-\(\)\d,]+\.\d{2})",
            line
        )
        if m:
            date_str, desc, amount_str = m.groups()
            date = parse_date(date_str)
            amount = parse_amount(amount_str)
            if date and amount is not None:
                transactions.append({
                    "date": date,
                    "amount": amount,
                    "description": desc.strip(),
                })

    return transactions


def parse_amex(text: str) -> List[Dict]:
    """Parse American Express statements."""
    transactions = []

    # Amex often has: MM/DD/YYYY DESCRIPTION AMOUNT
    lines = text.split("\n")
    for line in lines:
        m = re.search(
            r"(\d{1,2}/\d{1,2}/\d{2,4})\s+(.+?)\s+([\$\-\(\)\d,]+\.\d{2})",
            line
        )
        if m:
            date_str, desc, amount_str = m.groups()
            date = parse_date(date_str)
            amount = parse_amount(amount_str)
            if date and amount is not None:
                transactions.append({
                    "date": date,
                    "amount": amount,
                    "description": desc.strip(),
                })

    return transactions


def parse_capitalone(text: str) -> List[Dict]:
    """Parse Capital One statements."""
    transactions = []

    lines = text.split("\n")
    for line in lines:
        # MM/DD/YYYY DESCRIPTION AMOUNT
        m = re.search(
            r"(\d{1,2}/\d{1,2}/\d{2,4})\s+(.+?)\s+([\$\-\(\)\d,]+\.\d{2})",
            line
        )
        if m:
            date_str, desc, amount_str = m.groups()
            date = parse_date(date_str)
            amount = parse_amount(amount_str)
            if date and amount is not None:
                transactions.append({
                    "date": date,
                    "amount": amount,
                    "description": desc.strip(),
                })

    return transactions


def parse_usbank(text: str) -> List[Dict]:
    """Parse US Bank statements."""
    transactions = []

    lines = text.split("\n")
    for line in lines:
        m = re.search(
            r"(\d{1,2}/\d{1,2}/\d{2,4})\s+(.+?)\s+([\$\-\(\)\d,]+\.\d{2})",
            line
        )
        if m:
            date_str, desc, amount_str = m.groups()
            date = parse_date(date_str)
            amount = parse_amount(amount_str)
            if date and amount is not None:
                transactions.append({
                    "date": date,
                    "amount": amount,
                    "description": desc.strip(),
                })

    return transactions


# ──────────────────────────────────────────────────────────────────────────────
# Generic table-based parser (fallback)
# ──────────────────────────────────────────────────────────────────────────────

def parse_generic_tables(pdf_path: str) -> List[Dict]:
    """Extract transactions from tables using pdfplumber."""
    transactions = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue

                # Find header row - look for date/description/amount columns
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

                # Map columns
                header = table[header_row]
                date_col = desc_col = amount_col = None
                for j, col in enumerate(header):
                    if not col:
                        continue
                    col_lower = str(col).lower()
                    if "date" in col_lower or "posted" in col_lower:
                        date_col = j
                    elif "desc" in col_lower or "name" in col_lower or "payee" in col_lower or "memo" in col_lower:
                        desc_col = j
                    elif "amount" in col_lower or "debit" in col_lower or "credit" in col_lower:
                        amount_col = j

                if date_col is None or (desc_col is None and amount_col is None):
                    continue

                # Parse data rows
                for row in table[header_row + 1:]:
                    if not row or len(row) <= max(date_col, desc_col or 0, amount_col or 0):
                        continue

                    date_str = str(row[date_col]) if date_col < len(row) and row[date_col] else ""
                    desc = str(row[desc_col]) if desc_col is not None and desc_col < len(row) and row[desc_col] else ""
                    amount_str = str(row[amount_col]) if amount_col is not None and amount_col < len(row) and row[amount_col] else ""

                    date = parse_date(date_str)
                    amount = parse_amount(amount_str)

                    if date and amount is not None and desc:
                        transactions.append({
                            "date": date,
                            "amount": amount,
                            "description": desc.strip(),
                        })

    return transactions


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────────────

PARSERS = {
    "chase": parse_chase,
    "citi": parse_citi,
    "bofa": parse_bofa,
    "wells": parse_wells,
    "discover": parse_discover,
    "amex": parse_amex,
    "capitalone": parse_capitalone,
    "usbank": parse_usbank,
}


def parse_pdf_statement(pdf_path: str, bank_hint: Optional[str] = None) -> Tuple[List[Dict], str]:
    """
    Parse a bank statement PDF and return normalized transactions.

    Returns: (transactions, detected_bank)
    """
    # Extract text
    full_text = extract_all_text(pdf_path)

    # Detect bank
    bank = bank_hint or detect_bank(full_text)

    # Parse with bank-specific parser
    transactions = []
    if bank and bank in PARSERS:
        transactions = PARSERS[bank](full_text)

    # Fallback: generic table parser
    if not transactions:
        transactions = parse_generic_tables(pdf_path)

    # Final fallback: text-based regex extraction
    if not transactions:
        transactions = _parse_generic_text(full_text)

    # Deduplicate
    seen = set()
    unique = []
    for t in transactions:
        key = (t["date"], round(t["amount"], 2), t["description"][:50])
        if key not in seen:
            seen.add(key)
            unique.append(t)

    return unique, bank or "unknown"


def _parse_generic_text(text: str) -> List[Dict]:
    """Generic regex-based extraction from raw text."""
    transactions = []

    # Try to find lines with date + amount pattern
    lines = text.split("\n")
    for line in lines:
        # Look for date-like + amount-like on same line
        date_matches = list(re.finditer(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", line))
        if not date_matches:
            continue

        date_str = date_matches[0].group()
        date = parse_date(date_str)
        if not date:
            continue

        # Find amount on same line
        amount_match = re.search(r"[\$\-\(\)\d,]+\.\d{2}", line)
        if not amount_match:
            continue

        amount = parse_amount(amount_match.group())
        if amount is None:
            continue

        # Description is text between date and amount
        date_end = date_matches[0].end()
        amount_start = amount_match.start()
        desc = line[date_end:amount_start].strip(" -:")

        if desc:
            transactions.append({
                "date": date,
                "amount": amount,
                "description": desc,
            })

    return transactions


# ──────────────────────────────────────────────────────────────────────────────
# Preview/debug helpers
# ──────────────────────────────────────────────────────────────────────────────

def preview_pdf(pdf_path: str, max_chars: int = 3000) -> Dict:
    """Return preview info for debugging."""
    full_text = extract_all_text(pdf_path)
    bank = detect_bank(full_text)
    transactions, _ = parse_pdf_statement(pdf_path)

    return {
        "bank_detected": bank,
        "text_preview": full_text[:max_chars],
        "transaction_count": len(transactions),
        "sample_transactions": transactions[:5],
    }