---
status: backlog
priority: P2
agent_claimed: null
claimed_at: null
updated: 2026-08-20
---

# CSV Import and Transaction Categorization

> **Repo:** PERSONAL-FINANCE-DASHBOARD
> **Description:** Multi-bank CSV parser with ML-based category auto-tagging

---

## Context

Users upload CSV exports from their banks. Parse various bank formats, normalize fields, and auto-categorize transactions.

---

## Acceptance Criteria

- [ ] CSV parser handling 5+ bank formats (Chase, BoA, Fidelity, etc.) with format auto-detection
- [ ] ML-based category suggestion using transaction description + amount patterns
- [ ] Manual category override with learning feedback loop
- [ ] Duplicate transaction detection across imports

---

## Technical Notes

- FastAPI file upload; pandas for CSV parsing; scikit-learn for category prediction
