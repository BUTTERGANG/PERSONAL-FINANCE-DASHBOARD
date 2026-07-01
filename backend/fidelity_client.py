"""
Fidelity OFX Direct Connect client.

Uses the same protocol as Quicken — talks directly to Fidelity's OFX endpoint
with username/password. No browser, no 2FA prompt per pull.

If this fails, see THE-VISION/SECURITY.md → Troubleshooting Fidelity OFX.
"""

import logging
from datetime import datetime, timedelta, timezone
from io import BytesIO

from ofxtools.Client import OFXClient, StmtRq
from ofxtools.Parser import OFXTree
from ofxtools.utils import UTC

from .config import get_settings

logger = logging.getLogger(__name__)

FIDELITY_OFX_URL = "https://ofx.fidelity.com/ftgw/OFX/clients/download"
FIDELITY_FID = "7776"
FIDELITY_ORG = "FIDELITY"


def is_configured() -> bool:
    s = get_settings()
    return bool(s.fidelity_user and s.fidelity_pin and s.fidelity_account_id)


def fetch_transactions(days_back: int = 30) -> list[dict]:
    """
    Fetch Fidelity brokerage transactions via OFX direct connect.
    Returns a list of normalized transaction dicts.
    """
    if not is_configured():
        logger.warning("Fidelity OFX credentials not configured — skipping.")
        return []

    settings = get_settings()
    client = OFXClient(
        FIDELITY_OFX_URL,
        org=FIDELITY_ORG,
        fid=FIDELITY_FID,
        version=220,
        appid="QWIN",
        appver="2700",
    )

    dtstart = datetime.now(UTC) - timedelta(days=days_back)
    stmt_req = StmtRq(
        acctid=settings.fidelity_account_id,
        accttype="CHECKING",  # Use CHECKING for cash management; switch to MMMKT for money market
        dtstart=dtstart,
        dtend=None,
        include_transactions=True,
    )

    try:
        response = client.request_statements(
            settings.fidelity_user,
            settings.fidelity_pin,
            stmt_req,
            dryrun=False,
        )
        raw = response.read() if hasattr(response, "read") else response
    except Exception as exc:
        logger.error("Fidelity OFX request failed: %s", exc)
        raise

    try:
        parser = OFXTree()
        parser.parse(BytesIO(raw) if isinstance(raw, bytes) else BytesIO(raw.encode()))
        ofx = parser.convert()
    except Exception as exc:
        logger.error("Fidelity OFX parse failed: %s", exc)
        raise

    transactions = []
    for stmt in ofx.statements:
        for txn in stmt.transactions:
            transactions.append(
                {
                    "id": f"fidelity_{txn.fitid}",
                    "date": txn.dtposted.replace(tzinfo=timezone.utc)
                    if txn.dtposted.tzinfo is None
                    else txn.dtposted,
                    "amount": float(txn.trnamt),
                    "description": str(txn.name or txn.memo or "Fidelity Transaction"),
                    "type": str(txn.trntype),
                }
            )

    return transactions


def fetch_balance() -> float | None:
    """
    Fetch current Fidelity account balance via OFX.
    Returns None if not configured or on error.
    """
    if not is_configured():
        return None

    settings = get_settings()
    client = OFXClient(
        FIDELITY_OFX_URL,
        org=FIDELITY_ORG,
        fid=FIDELITY_FID,
        version=220,
        appid="QWIN",
        appver="2700",
    )

    stmt_req = StmtRq(
        acctid=settings.fidelity_account_id,
        accttype="CHECKING",
        include_transactions=False,
    )

    try:
        response = client.request_statements(settings.fidelity_user, settings.fidelity_pin, stmt_req)
        raw = response.read() if hasattr(response, "read") else response
        parser = OFXTree()
        parser.parse(BytesIO(raw) if isinstance(raw, bytes) else BytesIO(raw.encode()))
        ofx = parser.convert()
        for stmt in ofx.statements:
            if stmt.ledgerbal:
                return float(stmt.ledgerbal.balamt)
    except Exception as exc:
        logger.error("Fidelity balance fetch failed: %s", exc)

    return None
