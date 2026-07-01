# Security Model — Personal Finance Dashboard

## What's Protected and How

### Threat Model

This is a single-user personal finance app running on Replit. The realistic threats are:

1. **Someone gets your Replit account** → they see everything
2. **Database file is exposed** → they see encrypted tokens + transaction history
3. **Code repo is compromised** → code has no secrets, so limited damage
4. **Plaid token is stolen** → they can read your transactions (not move money)

### Defense in Depth

```
Layer 1: Access to Replit account
  → Protected by: Replit account password + 2FA (enable this!)
  → Recommendation: Use a unique strong password + GitHub SSO login

Layer 2: Secrets / credentials
  → Protected by: Replit Secrets (encrypted env vars, not in code or disk)
  → Never committed to git (.gitignore enforces this)
  → Encryption key only exists in Secrets panel

Layer 3: Database at rest
  → Protected by: Plaid tokens encrypted before write (Fernet AES-128-CBC)
  → finance.db alone is useless without the ENCRYPTION_KEY
  → OFX credentials are never stored in the DB at all (env vars only)

Layer 4: In-transit
  → Protected by: Replit provides TLS 1.3 for all public traffic
  → Internal traffic (Streamlit → FastAPI) is localhost, not exposed

Layer 5: Plaid access
  → Plaid access tokens are READ-ONLY by default
  → Cannot initiate transfers, bill pay, or any write operations
  → Even if a token were stolen, no money can be moved
```

---

## What's Encrypted

| Data | Where Stored | Encrypted? | How |
|------|-------------|-----------|-----|
| Plaid access tokens | SQLite (accounts table) | YES | Fernet (ENCRYPTION_KEY) |
| Transaction data | SQLite (transactions table) | No | Plain text |
| OFX username | Replit Secrets / env var | Yes (by Replit) | Never touches disk |
| OFX password/PIN | Replit Secrets / env var | Yes (by Replit) | Never touches disk |
| Plaid client secret | Replit Secrets / env var | Yes (by Replit) | Never touches disk |
| Encryption key | Replit Secrets / env var | Yes (by Replit) | Never touches disk |

**Why transaction data isn't encrypted:**
The SQLite file is on Replit's filesystem which is tied to your Replit account. Encrypting all 10,000+ transactions would add significant overhead for no meaningful added security — the real sensitive piece (tokens that grant access to the account) is encrypted. If encrypting transaction data becomes a priority, SQLCipher is the path forward (Phase 2 roadmap item).

---

## What's in Git (Safe to Commit)

- All Python source code — no secrets anywhere in the code
- requirements.txt
- .env.example (template with placeholder values, no real credentials)
- THE-VISION docs
- .replit, replit.nix
- .gitignore

**SAFE. The code alone gives an attacker nothing.**

---

## What's NEVER in Git

These are blocked by .gitignore — verify they are never staged:

- `.env` — real credentials
- `finance.db` — your transaction data
- Any file named `secrets*`, `*.key`, `*.pem`

Before every commit, run: `git status` and verify none of these appear.

---

## Recommended Security Hygiene

### Replit Account
- Enable 2FA on your Replit account — this is the single most important step
- Use a unique, strong password (not reused from other sites)
- Log out of Replit on shared computers

### GitHub Repo (if used)
- Keep the repo private
- Enable "Secret scanning" (GitHub → Settings → Code security)
- Only grant access to people who need it (see GITHUB-SETUP.md)
- Rotate access tokens if you ever accidentally share access

### Plaid Tokens
- If you believe a Plaid token is compromised: in Plaid dashboard → Items → remove the item
- Re-link the account — a new access token is issued

### Fidelity OFX
- If you change your Fidelity password, update `FIDELITY_PIN` in Replit Secrets
- Fidelity OFX has no way to rotate credentials separately from your main password

---

## Privacy: What Plaid Can See

Plaid is a third-party service used by Mint, YNAB, and most other finance apps.
By linking accounts through Plaid:
- Plaid can see your transaction history and balances
- Plaid's privacy policy governs how they handle this data
- Plaid does NOT have the ability to move money with the tokens we use (read-only product)

If you are uncomfortable with Plaid, the alternative for Chase/Citi/PayPal is browser scraping
(eebette/bank_scrapers, finance-dl) — but those break frequently and require re-authentication.
This is a real tradeoff, documented in THE-VISION/ROADMAP.md.

---

## Troubleshooting Fidelity OFX Errors

If you see `FIDELITY_SYNC_ERROR` in the sync logs:

1. **Auth error**: Your OFX credentials are wrong. Try:
   - Verify FIDELITY_USER and FIDELITY_PIN in Replit Secrets
   - Call Fidelity (800-343-3548) → ask to enable Quicken Direct Connect
   - They may need to issue a separate Direct Connect PIN

2. **Connection refused**: Fidelity's OFX endpoint may be temporarily down.
   - Check status at https://ofxhome.com/
   - Wait and retry

3. **Account not found**: Verify FIDELITY_ACCOUNT_ID is the correct account number
   (usually 9 digits, found on your Fidelity statements)
