# Setup Guide — From Zero to Running Dashboard

Follow this guide exactly once to get the app live on Replit.
After this, the app runs continuously and syncs automatically.

---

## Prerequisites

- Replit account with credits (Always On enabled)
- Plaid developer account (free at dashboard.plaid.com)
- Your Fidelity, Chase, Citi, PayPal, and Venmo login credentials

---

## Step 1: Create a Plaid Developer Account

1. Go to https://dashboard.plaid.com/signup
2. Sign up for a free account
3. Once in the dashboard, go to **Team Settings → Keys**
4. Copy your **Client ID** and **Sandbox Secret** — you'll need these
5. To connect real accounts later: go to **API → Request Development Access**
   - Fill out the form (personal use, single user)
   - Approval takes 1–5 business days
   - Until then, use `PLAID_ENV=sandbox` with test credentials

---

## Step 2: Generate Your Encryption Key

On your local machine or in the Replit shell:

```bash
python scripts/generate_key.py
```

This prints something like:
```
ENCRYPTION_KEY=abc123...your_key_here...xyz
```

**Copy the full key value.** You will add it to Replit Secrets in Step 4.
Never store this in your code or .env file on disk.

---

## Step 3: Push to Replit

### Option A: From GitHub (recommended)
1. Create your private GitHub repo (see GITHUB-SETUP.md)
2. Push this project to it
3. In Replit, click **+ Create Repl → Import from GitHub**
4. Select your private repo

### Option B: Direct Upload
1. In Replit, click **+ Create Repl → Upload Folder**
2. Upload the entire project folder

---

## Step 4: Add Secrets to Replit

In your Replit project, click the **Secrets** panel (lock icon in sidebar).
Add each of these key-value pairs:

| Secret Key | Where to Get the Value |
|-----------|----------------------|
| `PLAID_CLIENT_ID` | Plaid dashboard → Team Settings → Keys |
| `PLAID_SECRET` | Plaid dashboard → Team Settings → Keys (use Sandbox or Dev secret) |
| `PLAID_ENV` | `sandbox` (change to `development` when approved) |
| `FIDELITY_USER` | Your Fidelity username |
| `FIDELITY_PIN` | Your Fidelity password (see Fidelity note below) |
| `FIDELITY_ACCOUNT_ID` | Your Fidelity account number |
| `ENCRYPTION_KEY` | The key you generated in Step 2 |
| `SYNC_INTERVAL_HOURS` | `4` |
| `APP_BASE_URL` | Your Replit public URL (e.g., `https://finance.yourname.repl.co`) |

**Fidelity PIN note:** Fidelity's direct connect (OFX) sometimes uses a separate PIN from your web password.
- Try your regular password first
- If it fails, call Fidelity (800-343-3548) and ask to enable "Quicken Direct Connect"
- They will either confirm your password works or issue a Direct Connect PIN

---

## Step 5: Enable Always On

1. In your Replit project, click **Always On** in the sidebar
2. Toggle it on — this keeps the app running and the scheduler firing
3. This uses Replit credits; free tier apps sleep after inactivity

---

## Step 6: Run the App

Click the **Run** button in Replit, or in the Replit shell:

```bash
bash run.sh
```

Watch for:
```
🚀 Starting FastAPI backend on port 8000...
🖥️  Starting Streamlit frontend on port 8501...
```

Open the Replit webview — you'll see the Streamlit dashboard.

---

## Step 7: Link Your Accounts

1. In the dashboard, navigate to **Link Account** (sidebar)
2. Click **Link with Plaid** for each institution:
   - Chase → select "Chase" in Plaid Link
   - Citi → select "Citi" in Plaid Link
   - PayPal → select "PayPal" in Plaid Link
   - Venmo → select "Venmo" in Plaid Link
3. Complete the authentication in Plaid's interface (handles 2FA for you)
4. After linking, click **Sync Now** or wait for the next auto-sync

**For Fidelity:** The connection is automatic via OFX — no Plaid Link needed.
Navigate to **Accounts** and check if Fidelity shows "Last synced." If it shows
an error, check THE-VISION/SECURITY.md troubleshooting section.

---

## Step 8: Verify Everything is Working

1. Go to **Overview** — you should see your account balance cards
2. Go to **Transactions** — you should see recent transactions
3. Go to **Accounts** — check last synced timestamp on each account
4. Check **Settings → Sync Logs** to verify no errors

---

## Upgrading to Real Plaid Data

Once Plaid approves your Development access:
1. Go to Plaid dashboard → Team Settings → Keys → copy the **Development secret**
2. Update `PLAID_SECRET` in Replit Secrets to the development secret
3. Update `PLAID_ENV` from `sandbox` to `development`
4. Re-run the app
5. Re-link your accounts (development tokens are separate from sandbox)

---

## Updating the App

When code changes are pushed to GitHub:
1. In Replit, open the **Git** panel
2. Pull changes
3. The app auto-restarts (or click the Run button)

---

## Backup Your Data

Your transaction history lives in `finance.db` on Replit's persistent disk.
Replit persists this automatically, but for extra safety:

```bash
# In Replit shell — downloads a copy
cp finance.db finance_backup_$(date +%Y%m%d).db
```

Or use the **Export Data** option in the Settings page to download CSV files.
