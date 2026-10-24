# Changelog

All notable changes to PERSONAL-FINANCE-DASHBOARD. Newest first.

## 2026-10-23 — Security: dependency vulnerability fixes

Known advisories (OSV) in lockfiles: **15 high, 13 moderate, 6 low, 14 unrated → 2 moderate**.

- `requirements.txt`: `cryptography` 44.0.0 → 50.0.2, `python-multipart` 0.0.32, `python-dotenv` 1.2.4
- `react-frontend`: **`vite` ^6.4.5** + `@vitejs/plugin-react` ^4.7.0; `npm audit fix`
- Critical/high advisories cleared in: `browserslist`, `cryptography`, `nanoid`, `postcss`, `python-multipart`, `source-map-js`, `vite`
- Verified: 51 tests pass (45 skipped: need sample statement PDFs) on Python 3.11; frontend build passes. Note: the API tests need `httpx`, which isn't in `requirements.txt`
