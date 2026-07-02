# Security Architecture — Personal Finance Dashboard

## Threat Model

**Assets we protect:**
1. Plaid access tokens (read-only, but grant access to all transaction history)
2. Fidelity OFX credentials (username/password)
3. Transaction history & financial data
4. Encryption key (master key for all Plaid tokens)

**Attackers:**
- External: Compromised Replit container, stolen DB file, intercepted traffic
- Internal: Malicious dependency, supply chain attack
- Accidental: Leaking secrets to git, logs, error messages

**Assumptions:**
- Replit provides HTTPS at the edge
- SQLite file persists on Replit's disk (not ephemeral)
- Only the frontend port (5173) is public; API port (8000) is internal
- Single user — no multi-tenant isolation needed

---

## Defense in Depth

### 1. Plaid Tokens — Encrypted at Rest (Fernet AES-128)
```
Plaintext access_token → encrypt(key) → ciphertext → SQLite
```
- Encryption key (`ENCRYPTION_KEY`) lives **only** in Replit Secrets / env var
- Never written to disk, never in code, never in git
- DB file alone is useless without the key
- On token compromise: revoke in Plaid dashboard → re-link account

### 2. Fidelity OFX Credentials — Env Vars Only
- `FIDELITY_USER`, `FIDELITY_PIN`, `FIDELITY_ACCOUNT_ID` in Replit Secrets
- Used in-memory by `fidelity_client.py`; never written to DB or logs
- If compromised: change Fidelity password + update Replit Secrets

### 3. Transport Security
- Replit terminates TLS at the edge → all external traffic is HTTPS
- Internal Replit traffic (frontend → backend) is on private network
- No sensitive data in URLs (all POST bodies or headers)

### 4. Plaid Product Scope — Read-Only
- We request `transactions` + `balance` products only
- **No `transfer` or `payment_initiation` products** → tokens cannot move money
- Even if token is stolen, attacker can only *read*, not write

### 5. Frontend Port Only Public
- Replit maps port 5173 → public port 80
- Port 8000 (FastAPI) is `exposeLocalhost = true` but not publicly routed
- Attacker would need to hit the frontend, which proxies `/api` to backend

---

## What's Safe to Commit

| File | Safe? | Reason |
|------|-------|--------|
| All `.py`, `.tsx`, `.ts`, `.css` | ✅ | No secrets, only logic |
| `requirements.txt`, `package.json` | ✅ | Dependency manifests |
| `run.sh`, `.replit`, `replit.nix` | ✅ | Config, no secrets |
| `THE-VISION/*.md` | ✅ | Documentation |
| `.env.example` | ✅ | Template only, placeholder values |
| `finance.db` | ❌ | **Git-ignored** — contains encrypted tokens + real transaction data |
| `.env` | ❌ | **Git-ignored** — would contain real secrets if created locally |
| `ENCRYPTION_KEY` value | ❌ | **Never** — only in Replit Secrets |

---

## Key Rotation Procedure

**If `ENCRYPTION_KEY` is compromised:**
1. Generate new key: `python scripts/generate_key.py`
2. Decrypt all tokens with old key, re-encrypt with new key (one-time script)
3. Update Replit Secrets with new key
4. Restart app

**If Plaid access token is compromised:**
1. Plaid Dashboard → Team Settings → Items → Remove the item
2. User re-links account via dashboard → new token issued

**If Fidelity credentials are compromised:**
1. Change Fidelity password
2. Update `FIDELITY_PIN` in Replit Secrets
3. Restart app

---

## Dependency Security

```bash
# Check for vulnerabilities
pip-audit  # Python
npm audit  # Node (run in react-frontend/)
```

- Pin dependencies in `requirements.txt` and `package-lock.json`
- Update monthly or when CVEs announced
- No `devDependencies` in production image

---

## Logging & Secrets Hygiene

- **Never log** Plaid tokens, Fidelity credentials, or encryption key
- `sync.py` logs only: institution name, transaction counts, error messages (no token values)
- FastAPI access logs go to stdout — Replit captures them; ensure no secrets in query params
- Plaid `public_token` is short-lived (30 min) and single-use — safe in browser network tab

---

## Troubleshooting Fidelity OFX Errors

If you see `FIDELITY_SYNC_ERROR` in the sync logs:

### 1. Auth Error
Your OFX credentials are wrong. Try:
- Verify `FIDELITY_USER` and `FIDELITY_PIN` in Replit Secrets
- Call Fidelity (800-343-3548) → ask to enable **Quicken Direct Connect**
- They may need to issue a separate Direct Connect PIN

### 2. Connection Refused
Fidelity's OFX endpoint may be temporarily down.
- Check status at https://ofxhome.com/
- Wait and retry

### 3. Account Not Found
- Verify `FIDELITY_ACCOUNT_ID` is the correct account number
- Usually 9 digits, found on Fidelity statements

---

## Privacy: What Plaid Can See

Plaid is a third-party service used by Mint, YNAB, and most other finance apps.
By linking accounts through Plaid:
- Plaid can see your transaction history and balances
- Plaid's privacy policy governs how they handle this data
- Plaid does **NOT** have the ability to move money with the tokens we use (read-only product)

If you are uncomfortable with Plaid, the alternative for Chase/Citi/PayPal is browser scraping
(eebette/bank_scrapers, finance-dl) — but those break frequently and require re-authentication.
This is a real tradeoff, documented in THE-VISION/ROADMAP.md.

---

## Future Hardening (Phase 2+)

- [ ] **SQLCipher**: Encrypt the entire SQLite file, not just tokens
- [ ] **App-level PIN**: Simple passphrase gate on the dashboard UI
- [ ] **Audit log**: Record every dashboard access (IP, timestamp)
- [ ] **Dependency scanning**: GitHub Actions with Dependabot alerts