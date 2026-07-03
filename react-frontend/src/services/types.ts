// API response shapes — mirror of the FastAPI Pydantic schemas.
// Sign convention: transaction `amount` is POSITIVE for spend/debit,
// NEGATIVE for credit/refund. Credit/loan accounts count as debt.

export interface Account {
  id: string;
  name: string;
  institution: string;
  account_type: string; // checking | savings | credit | investment | loan | asset | cash
  balance: number;
  available_balance: number | null;
  currency: string;
  last_synced: string | null;
  created_at: string | null;
}

export interface Transaction {
  id: string;
  account_id: string;
  date: string; // ISO datetime
  amount: number;
  description: string;
  category: string | null;
  merchant: string | null;
  pending: boolean;
  source: string; // plaid | ofx | csv
}

export interface SpendingSummaryRow {
  category: string;
  total: number;
}

export interface MoMCategory {
  category: string;
  this_month: number;
  last_month_same_point: number;
  last_month_total: number;
  pct_change: number | null;
}

export interface MonthOverMonth {
  month: string;
  prev_month: string;
  day_of_month: number;
  categories: MoMCategory[];
  total_this_month: number;
  total_last_month_same_point: number;
}

export interface NetWorthSnapshot {
  day: string; // YYYY-MM-DD
  net_worth: number;
  total_assets: number;
  total_debt: number;
}

export interface Budget {
  category: string;
  limit_amount: number;
  spent: number;
  remaining: number;
  pct: number;
  alert: 'warning' | 'danger' | null;
}

export interface BudgetAlert {
  category: string;
  level: 'warning' | 'danger';
  spent: number;
  limit: number;
  pct: number;
  message: string;
}

export interface Subscription {
  merchant_key: string;
  merchant: string;
  category: string;
  amount: number;
  frequency: 'weekly' | 'biweekly' | 'monthly' | 'quarterly' | 'annual';
  occurrences: number;
  last_date: string;
  monthly_cost: number;
  est_annual: number;
}

export interface SyncLog {
  id: number;
  account_id: string | null;
  institution: string;
  status: 'success' | 'error';
  transactions_added: number;
  error_message: string | null;
  synced_at: string;
}

export interface ImportTxnRow {
  date: string;
  amount: number;
  description: string;
  category?: string | null;
}

export interface ImportResult {
  status: string;
  added: number;
  skipped_duplicates: number;
}

export interface Health {
  status: string;
  sync_interval_hours: number;
}

// PDF import types
export interface ParsedTransaction {
  date: string; // YYYY-MM-DD
  amount: number;
  description: string;
  category?: string | null;
}

export interface PDFPreviewResponse {
  bank_detected: string;
  transactions: ParsedTransaction[];
  transaction_count: number;
}
