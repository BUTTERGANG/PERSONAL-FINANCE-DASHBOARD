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
} from './types';

// Dev: Vite proxies /api → :8000. Prod: same-origin /api (adjust if the backend
// is hosted elsewhere on Replit).
const BASE_URL = '/api';

// Raw absolute base for links the browser navigates to directly (Plaid Link).
export const API_ORIGIN = import.meta.env.DEV ? 'http://localhost:8000' : '';

async function get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const qs = params
    ? '?' +
      new URLSearchParams(
        Object.fromEntries(
          Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
        ) as Record<string, string>,
      ).toString()
    : '';
  const res = await fetch(`${BASE_URL}${path}${qs}`);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

async function send<T>(path: string, method: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status}`);
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

// Plaid Link is a server-rendered HTML page the browser navigates to directly.
export const plaidLinkUrl = () => `${API_ORIGIN}/api/plaid/link`;
