import type {
  Account,
  Transaction,
  SpendingSummaryRow,
  MonthOverMonth,
  NetWorthSnapshot,
  Budget,
  BudgetAlert,
  Subscription,
  SyncLog,
  ImportTxnRow,
  ImportResult,
  Health,
  ParsedTransaction,
  PDFPreviewResponse,
  PdfImportResult,
  CategoryRule,
} from './types';

import { pinHeader, clearPin } from './pin';

// Dev: Vite proxies /api → :8000. Prod: same-origin /api (adjust if the backend
// is hosted elsewhere on Replit).
const BASE_URL = '/api';

// Raw absolute base for links the browser navigates to directly (Plaid Link).
export const API_ORIGIN = import.meta.env.DEV ? 'http://localhost:8000' : '';

/**
 * A 401 means the stored PIN is missing/stale — clear it so the app re-locks
 * and prompts again. onPinChange listeners (the AuthGate) react to this.
 */
function handleUnauthorized(res: Response): void {
  if (res.status === 401) clearPin();
}

async function get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const qs = params
    ? '?' +
      new URLSearchParams(
        Object.fromEntries(
          Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
        ) as Record<string, string>,
      ).toString()
    : '';
  const res = await fetch(`${BASE_URL}${path}${qs}`, { headers: { ...pinHeader() } });
  if (!res.ok) {
    handleUnauthorized(res);
    throw new Error(`GET ${path} → ${res.status}`);
  }
  return res.json();
}

async function send<T>(path: string, method: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...pinHeader(),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    handleUnauthorized(res);
    throw new Error(`${method} ${path} → ${res.status}`);
  }
  return res.json();
}

// --- Accounts ---
export const fetchAccounts = () => get<Account[]>('/accounts/');

// --- Transactions ---
export const fetchTransactions = (params: {
  days?: number;
  account_id?: string;
  search?: string;
  category?: string;
} = {}) => get<Transaction[]>('/transactions/', params);
export const fetchSpendingSummary = (days = 30) =>
  get<SpendingSummaryRow[]>('/transactions/summary', { days });
export const fetchMonthOverMonth = () => get<MonthOverMonth>('/transactions/mom');
export const fetchCategories = () => get<string[]>('/transactions/categories');

// --- Categorization ---
export const updateTransactionCategory = (
  id: string,
  category: string | null,
  apply_to_merchant = true,
) =>
  send<{ status: string; category: string | null; rows_updated: number }>(
    `/transactions/${id}`,
    'PATCH',
    { category, apply_to_merchant },
  );
export const autoCategorize = () =>
  send<{ status: string; categorized: number; still_uncategorized: number }>(
    '/transactions/auto-categorize',
    'POST',
  );
export const fetchCategoryRules = () => get<CategoryRule[]>('/transactions/rules');
export const deleteCategoryRule = (merchant_key: string) =>
  send<{ status: string }>(`/transactions/rules/${encodeURIComponent(merchant_key)}`, 'DELETE');

// --- Net worth ---
export const fetchNetWorthSnapshots = (days = 365) =>
  get<NetWorthSnapshot[]>('/networth/snapshots', { days });

// --- Budgets ---
export const fetchBudgets = () => get<Budget[]>('/budgets/');
export const fetchBudgetAlerts = () => get<BudgetAlert[]>('/budgets/alerts');
export const setBudget = (category: string, limit_amount: number) =>
  send<Budget>('/budgets/', 'POST', { category, limit_amount });
export const deleteBudget = (category: string) =>
  send<{ status: string }>(`/budgets/${encodeURIComponent(category)}`, 'DELETE');

// --- Subscriptions ---
export const fetchSubscriptions = () => get<Subscription[]>('/subscriptions/');
export const ignoreSubscription = (merchant_key: string) =>
  send<{ status: string; merchant_key: string }>('/subscriptions/ignore', 'POST', {
    merchant_key,
  });
export const unignoreSubscription = (merchant_key: string) =>
  send<{ status: string; merchant_key: string }>(
    `/subscriptions/ignore/${encodeURIComponent(merchant_key)}`,
    'DELETE',
  );

// --- Manual accounts + import ---
export const createManualAccount = (name: string, account_type: string, balance: number) =>
  send<{ id: string; status: string }>('/manual/accounts', 'POST', {
    name,
    account_type,
    balance,
  });
export const updateManualBalance = (account_id: string, balance: number) =>
  send<{ id: string; balance: number; status: string }>(
    `/manual/accounts/${account_id}`,
    'PATCH',
    { balance },
  );
export const importTransactions = (account_id: string, transactions: ImportTxnRow[]) =>
  send<ImportResult>('/manual/import', 'POST', { account_id, transactions });

// --- PDF import ---
export const previewPdfImport = (file: File, bank_hint?: string) => {
  const form = new FormData();
  form.append('file', file);
  if (bank_hint) form.append('bank_hint', bank_hint);
  return fetch(`${BASE_URL}/manual/import-pdf/preview`, {
    method: 'POST',
    headers: { ...pinHeader() }, // NB: no Content-Type — browser sets multipart boundary
    body: form,
  }).then((res) => {
    if (!res.ok) {
      handleUnauthorized(res);
      throw new Error(`PDF preview failed: ${res.status}`);
    }
    return res.json() as Promise<PDFPreviewResponse>;
  });
};

export const confirmPdfImport = (
  account_id: string,
  transactions: ParsedTransaction[],
  set_balance?: number,
) =>
  send<PdfImportResult>('/manual/import-pdf/confirm', 'POST', {
    account_id,
    transactions,
    ...(set_balance != null ? { set_balance } : {}),
  });

// --- Sync ---
export const fetchSyncLogs = (limit = 20) => get<SyncLog[]>('/sync/logs', { limit });
export const triggerSync = () => send<{ status: string }>('/sync/trigger', 'POST');
export const triggerSyncRealtime = () =>
  send<Record<string, unknown>>('/sync/trigger?force_realtime=true', 'POST');

// --- Health --- (mounted at /health, not under /api)
export const fetchHealth = async (): Promise<Health | null> => {
  try {
    const res = await fetch(`${API_ORIGIN}/health`);
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
};

// --- PIN gate ---
// Whether the backend requires a PIN. Reads /health (always open). If /health is
// unreachable (e.g. proxy only forwards /api), we fall back to probing a guarded
// endpoint below.
export async function fetchPinRequired(): Promise<boolean> {
  const h = await fetchHealth();
  if (h && typeof (h as Health & { pin_required?: boolean }).pin_required === 'boolean') {
    return (h as Health & { pin_required: boolean }).pin_required;
  }
  // Fallback: hit a guarded endpoint with no PIN. 401 → gate is on.
  try {
    const res = await fetch(`${BASE_URL}/accounts/`);
    return res.status === 401;
  } catch {
    return false;
  }
}

/**
 * Try a PIN against a guarded endpoint. Stores it on success (so subsequent
 * calls carry it) and returns true; returns false on 401.
 */
export async function verifyPin(pin: string): Promise<boolean> {
  const res = await fetch(`${BASE_URL}/accounts/`, { headers: { 'X-Dashboard-Pin': pin } });
  return res.ok;
}

// Plaid Link is a server-rendered HTML page the browser navigates to directly.
export const plaidLinkUrl = () => `${API_ORIGIN}/api/plaid/link`;
