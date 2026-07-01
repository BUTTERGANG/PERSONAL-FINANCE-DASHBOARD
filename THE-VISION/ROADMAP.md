# Roadmap — Personal Finance Dashboard

## MVP (Built ✅)

The foundation is complete. These features are live:

- [x] Plaid integration for Chase, Citi, PayPal, Venmo
- [x] Fidelity OFX direct connect (no 2FA)
- [x] Encrypted Plaid token storage at rest
- [x] SQLite database (accounts, transactions, sync logs)
- [x] Background auto-sync every 4 hours
- [x] Manual sync trigger
- [x] FastAPI REST backend with all endpoints
- [x] Streamlit dashboard — 5 pages
- [x] Net worth overview with account balance cards
- [x] Spending by category (pie chart)
- [x] Spending over time (bar chart)
- [x] Transaction table with filters (date, account, category, search)
- [x] Account management page with sync status
- [x] Settings page with sync logs
- [x] Data export (CSV)
- [x] THE-VISION documentation suite
- [x] GitHub private repo setup guide
- [x] Replit deployment configuration

---

## Phase 2 — Polish & Intelligence

Nice-to-haves once the MVP is stable and accounts are flowing.

### UI Upgrade
- [ ] Port frontend from Streamlit to React + Tremor/shadcn
  - Custom card layout with institution logos
  - More control over spacing and typography
  - Better mobile responsiveness
- [ ] Dark/light theme toggle
- [ ] Collapsible sidebar with account icons

### Data Intelligence
- [ ] Budget tracking: set monthly budget per category, show progress bars
- [ ] Spending alerts: notify (email or push) when category exceeds budget
- [ ] Recurring transaction detection: automatically identify subscriptions
- [ ] Month-over-month comparison: "You spent 18% more on Food this month"
- [ ] Net worth trend: line chart of total net worth over time (requires snapshots)

### Security Upgrades
- [ ] SQLCipher: encrypt the entire SQLite file, not just tokens
- [ ] App-level password: simple PIN or passphrase to open the dashboard
- [ ] Audit log: record every time the dashboard is accessed

### Data
- [ ] Historical import: allow CSV upload from bank statements to backfill history
- [ ] Transaction categorization override: let user re-categorize transactions
- [ ] Merchant normalization: "AMZN*12345" → "Amazon"

---

## Phase 3 — Advanced

For when this becomes a serious tool.

### New Data Sources
- [ ] Venmo via direct scraping (Plaid's Venmo connection has gaps)
- [ ] Betterment / Wealthfront via OFX or scraping
- [ ] Real estate value (Zillow API for home equity tracking)
- [ ] Crypto holdings (Coinbase API, CoinGecko for prices)
- [ ] Manual accounts: enter 401k, car value, mortgage balance

### Infrastructure
- [ ] Migrate to Postgres (when data volume grows)
- [ ] Docker Compose setup (for running locally without Replit)
- [ ] Scheduled database backups to S3 or Google Drive
- [ ] GitHub Actions CI: lint, type check, test on every push

### Analytics
- [ ] Annual spending report (PDF export)
- [ ] Tax-year summaries by category
- [ ] Investment return tracking (Fidelity positions vs cost basis)
- [ ] Cash flow projection: based on recurring transactions, project next 30 days

---

## Known Limitations / Deferred Decisions

| Issue | Status | Plan |
|-------|--------|------|
| Transaction data not encrypted | Deferred | Phase 2: SQLCipher |
| Venmo transaction detail from Plaid is limited | Known | Phase 3: direct scraping |
| Fidelity investment positions not pulled (only transactions) | Deferred | Phase 2: add InvStmtRq for positions |
| No auth on dashboard UI | Intentional for now | Phase 2: simple PIN gate |
| Plaid Sandbox → Development requires manual approval | Pending | User to request dev access |
