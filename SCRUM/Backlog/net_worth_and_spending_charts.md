---
status: backlog
priority: P2
agent_claimed: null
claimed_at: null
updated: 2026-08-20
---

# Net Worth and Spending Charts

> **Repo:** PERSONAL-FINANCE-DASHBOARD
> **Description:** Recharts dashboard -- net worth timeline, spending by category, cash flow

---

## Context

Users need visual insights into their finances over time. Charts for net worth trajectory, spending breakdowns, and cash flow patterns.

---

## Acceptance Criteria

- [ ] Net worth timeline chart with assets/liabilities breakdown
- [ ] Spending by category pie/bar chart with month-over-month comparison
- [ ] Cash flow calendar showing daily income/expense balance
- [ ] Custom date range picker with preset ranges (1m/3m/6m/1y/YTD)

---

## Technical Notes

- FastAPI aggregation endpoints; Recharts for React charts; SQLite window functions for trends
