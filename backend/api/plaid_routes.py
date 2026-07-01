"""
Plaid integration endpoints.

GET  /api/plaid/link       — Serves an HTML page with Plaid Link JS for account linking.
POST /api/plaid/exchange   — Receives public_token, exchanges for access_token, stores encrypted.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import get_settings
from ..crypto import encrypt
from ..database import get_db
from ..models import Account
from ..plaid_client import create_link_token, exchange_public_token, fetch_accounts

router = APIRouter()

_UTC = timezone.utc


@router.get("/link", response_class=HTMLResponse)
def plaid_link_page():
    """
    Serves a self-contained HTML page that runs the Plaid Link flow.
    User lands here from Streamlit, completes auth, and is redirected back.
    """
    settings = get_settings()
    try:
        link_token = create_link_token()
    except Exception as exc:
        return HTMLResponse(
            f"<h2>Plaid Error</h2><p>{exc}</p>"
            "<p>Check that PLAID_CLIENT_ID and PLAID_SECRET are set in Replit Secrets.</p>",
            status_code=500,
        )

    backend_url = settings.backend_url
    app_url = settings.app_base_url

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Link Bank Account</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #0f0f14; color: #f1f5f9; display: flex;
           align-items: center; justify-content: center; min-height: 100vh; }}
    .card {{ background: #1a1a24; border: 1px solid #2d2d3d; border-radius: 16px;
             padding: 40px; max-width: 480px; width: 100%; text-align: center; }}
    h1 {{ font-size: 1.5rem; margin-bottom: 8px; }}
    p {{ color: #94a3b8; margin-bottom: 24px; font-size: 0.95rem; }}
    button {{ background: #7c3aed; color: white; border: none; padding: 14px 32px;
              border-radius: 10px; font-size: 1rem; cursor: pointer; width: 100%; }}
    button:hover {{ background: #6d28d9; }}
    button:disabled {{ background: #4b5563; cursor: not-allowed; }}
    .status {{ margin-top: 20px; padding: 14px; border-radius: 8px; display: none; font-size: 0.9rem; }}
    .success {{ background: #14532d; color: #86efac; display: block; }}
    .error   {{ background: #7f1d1d; color: #fca5a5; display: block; }}
    .spinner {{ display: none; margin: 16px auto; width: 32px; height: 32px;
                border: 3px solid #374151; border-top-color: #7c3aed;
                border-radius: 50%; animation: spin 0.8s linear infinite; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    .institution-label {{ background: #1e1e2e; border: 1px solid #374151; border-radius: 8px;
                          padding: 10px 16px; margin-bottom: 16px; font-size: 0.85rem; }}
    label {{ color: #94a3b8; font-size: 0.85rem; display: block; margin-bottom: 8px; text-align: left; }}
    input {{ width: 100%; background: #0f0f14; border: 1px solid #374151; color: #f1f5f9;
             padding: 10px 14px; border-radius: 8px; font-size: 0.9rem; margin-bottom: 16px; }}
  </style>
</head>
<body>
<div class="card">
  <h1>🔗 Link Bank Account</h1>
  <p>Securely connect your account using Plaid.<br/>Your credentials never touch our servers.</p>

  <label for="institution-name">Institution name (e.g. Chase, Citi, PayPal)</label>
  <input type="text" id="institution-name" placeholder="Chase" />

  <button id="link-btn" onclick="openPlaid()">Connect Account</button>
  <div class="spinner" id="spinner"></div>
  <div class="status" id="status"></div>
</div>

<script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
<script>
  const LINK_TOKEN = "{link_token}";
  const BACKEND   = "{backend_url}";
  const APP_URL   = "{app_url}";

  let handler;

  function openPlaid() {{
    const institutionName = document.getElementById("institution-name").value.trim() || "Unknown";
    if (!handler) {{
      handler = Plaid.create({{
        token: LINK_TOKEN,
        onSuccess: async (public_token, metadata) => {{
          setStatus("Linking account...", "");
          showSpinner(true);
          try {{
            const res = await fetch(BACKEND + "/api/plaid/exchange", {{
              method: "POST",
              headers: {{ "Content-Type": "application/json" }},
              body: JSON.stringify({{ public_token, institution_name: institutionName }}),
            }});
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Exchange failed");
            setStatus(
              "✅ Linked " + data.linked + " account(s): " + data.accounts.join(", ") +
              ". Returning to dashboard...",
              "success"
            );
            setTimeout(() => window.location.href = APP_URL, 2500);
          }} catch (err) {{
            setStatus("❌ " + err.message, "error");
          }} finally {{
            showSpinner(false);
          }}
        }},
        onExit: (err) => {{
          if (err) setStatus("❌ Plaid exit: " + err.display_message, "error");
        }},
      }});
    }}
    handler.open();
  }}

  function setStatus(msg, cls) {{
    const el = document.getElementById("status");
    el.textContent = msg;
    el.className = "status " + cls;
  }}

  function showSpinner(show) {{
    document.getElementById("spinner").style.display = show ? "block" : "none";
    document.getElementById("link-btn").disabled = show;
  }}
</script>
</body>
</html>""")


class ExchangeRequest(BaseModel):
    public_token: str
    institution_name: str


@router.post("/exchange")
def exchange_token(req: ExchangeRequest, db: Session = Depends(get_db)):
    try:
        result = exchange_public_token(req.public_token)
        access_token = result["access_token"]
        item_id = result["item_id"]

        # fetch_accounts uses /accounts/get (free) not /accounts/balance/get ($0.10/call)
        accounts = fetch_accounts(access_token)
        linked_names = []

        for acct in accounts:
            existing = db.get(Account, acct["account_id"])
            if existing:
                existing.plaid_access_token_enc = encrypt(access_token)
                existing.plaid_item_id = item_id
                existing.balance = acct["balances"]["current"] or 0.0
                existing.available_balance = acct["balances"]["available"]
                existing.last_synced = datetime.now(_UTC)
            else:
                db.add(
                    Account(
                        id=acct["account_id"],
                        name=acct["name"],
                        institution=req.institution_name.lower().replace(" ", "_"),
                        account_type=acct["type"],
                        balance=acct["balances"]["current"] or 0.0,
                        available_balance=acct["balances"]["available"],
                        plaid_access_token_enc=encrypt(access_token),
                        plaid_item_id=item_id,
                        last_synced=datetime.now(_UTC),
                        created_at=datetime.now(_UTC),
                    )
                )
            linked_names.append(acct["name"])

        db.commit()
        return {"linked": len(accounts), "accounts": linked_names}

    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
