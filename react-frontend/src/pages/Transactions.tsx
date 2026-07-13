import { useMemo, useState } from 'react';
import { Download, Wand2 } from 'lucide-react';
import {
  fetchAccounts,
  fetchCategories,
  fetchTransactions,
  updateTransactionCategory,
  autoCategorize,
} from '../services/api';
import { useAsync } from '../hooks/useAsync';
import type { Account, Transaction } from '../services/types';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import StatCard from '../components/StatCard';
import Money from '../components/Money';
import Badge from '../components/Badge';
import Spinner from '../components/Spinner';
import DataTable, { type Column } from '../components/DataTable';
import BarCategory from '../components/charts/BarCategory';
import AreaTrend from '../components/charts/AreaTrend';
import './Transactions.css';

const PERIODS = [7, 30, 60, 90, 365];

// Stable dot color per category. Semantic buckets use semantic tokens; spend
// categories use a fixed hue each so the same category reads the same everywhere.
const CATEGORY_HUE: Record<string, string> = {
  'Entertainment': '#8b5cf6',
  'Food and Drink': '#f59e0b',
  'Groceries': '#16a34a',
  'Health and Fitness': '#ec4899',
  'Shopping': '#0ea5e9',
  'Travel': '#14b8a6',
  'Income': 'var(--positive)',
  'Transfer': '#6366f1',
  'Payment': '#64748b',
  'Fees & Interest': 'var(--negative)',
  'Cash & ATM': '#a16207',
  'Subscriptions': 'var(--accent)',
  'Other': 'var(--text-muted)',
};

// Inline category editor — a dropdown styled as a chip that PATCHes on change.
function CategoryCell({
  txn,
  categories,
  onChange,
}: {
  txn: Transaction;
  categories: string[];
  onChange: (id: string, category: string | null) => void;
}) {
  const value = txn.category ?? '';
  const hue = value ? CATEGORY_HUE[value] ?? 'var(--text-muted)' : 'transparent';
  return (
    <div className="cat-cell" data-uncategorized={value ? undefined : 'true'}>
      <span className="cat-dot" style={{ background: hue }} aria-hidden />
      <select
        className="cat-select"
        value={value}
        onChange={(e) => onChange(txn.id, e.target.value || null)}
        aria-label="Category"
      >
        <option value="">Uncategorized</option>
        {categories.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
    </div>
  );
}

export default function Transactions() {
  const [days, setDays] = useState(30);
  const [accountId, setAccountId] = useState('');
  const [category, setCategory] = useState('');
  const [search, setSearch] = useState('');

  const accountsQ = useAsync<Account[]>(fetchAccounts);
  const categoriesQ = useAsync<string[]>(fetchCategories);
  const txnsQ = useAsync<Transaction[]>(
    () => fetchTransactions({ days, account_id: accountId, category, search }),
    [days, accountId, category, search],
  );

  const accounts = accountsQ.data ?? [];
  const categories = categoriesQ.data ?? [];
  const txns = txnsQ.data ?? [];

  const [autocatting, setAutocatting] = useState(false);
  const [notice, setNotice] = useState('');
  const uncategorizedCount = txns.filter((t) => !t.category).length;

  async function changeCategory(id: string, category: string | null) {
    // Learn a merchant rule and propagate (apply_to_merchant defaults true).
    try {
      const res = await updateTransactionCategory(id, category);
      if (res.rows_updated > 1) {
        setNotice(`Updated ${res.rows_updated} transactions from this merchant.`);
      }
      txnsQ.reload();
      categoriesQ.reload();
    } catch (e) {
      setNotice(e instanceof Error ? e.message : 'Could not update category.');
    }
  }

  async function runAutoCategorize() {
    setAutocatting(true);
    setNotice('');
    try {
      const res = await autoCategorize();
      setNotice(
        `Auto-categorized ${res.categorized} transaction${res.categorized === 1 ? '' : 's'}` +
          (res.still_uncategorized > 0 ? ` · ${res.still_uncategorized} still need a category.` : '.'),
      );
      txnsQ.reload();
    } catch (e) {
      setNotice(e instanceof Error ? e.message : 'Auto-categorize failed.');
    } finally {
      setAutocatting(false);
    }
  }

  const acctName = useMemo(
    () => Object.fromEntries(accounts.map((a) => [a.id, a.name])),
    [accounts],
  );

  // Summary stats
  const spend = txns.filter((t) => t.amount > 0);
  const credit = txns.filter((t) => t.amount < 0);
  const totalSpent = spend.reduce((s, t) => s + t.amount, 0);
  const totalCredit = credit.reduce((s, t) => s + Math.abs(t.amount), 0);
  const largest = spend.reduce((m, t) => Math.max(m, t.amount), 0);

  // Category breakdown (top 10 by spend)
  const byCategory = useMemo(() => {
    const map = new Map<string, number>();
    for (const t of spend) {
      const key = t.category || 'Uncategorized';
      map.set(key, (map.get(key) ?? 0) + t.amount);
    }
    return [...map.entries()]
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10)
      .reverse(); // horizontal bars read bottom-up
  }, [spend]);

  // Spend over time (by day)
  const overTime = useMemo(() => {
    const map = new Map<string, number>();
    for (const t of spend) {
      const day = t.date.slice(0, 10);
      map.set(day, (map.get(day) ?? 0) + t.amount);
    }
    return [...map.entries()]
      .map(([day, amount]) => ({ day: day.slice(5), amount }))
      .sort((a, b) => (a.day < b.day ? -1 : 1));
  }, [spend]);

  function exportCsv() {
    const header = ['date', 'description', 'amount', 'category', 'account', 'type', 'status', 'source'];
    const lines = txns.map((t) =>
      [
        t.date.slice(0, 10),
        `"${t.description.replace(/"/g, '""')}"`,
        t.amount.toFixed(2),
        t.category ?? '',
        acctName[t.account_id] ?? t.account_id,
        t.amount > 0 ? 'Debit' : 'Credit',
        t.pending ? 'Pending' : 'Settled',
        t.source,
      ].join(','),
    );
    const blob = new Blob([[header.join(','), ...lines].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transactions_${days}d.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const columns: Column<Transaction>[] = [
    {
      key: 'date',
      header: 'Date',
      sortable: true,
      sortValue: (t) => t.date,
      render: (t) => <span className="tnum">{t.date.slice(0, 10)}</span>,
    },
    { key: 'description', header: 'Description', render: (t) => t.description },
    {
      key: 'amount',
      header: 'Amount',
      numeric: true,
      sortable: true,
      sortValue: (t) => t.amount,
      render: (t) => <Money value={t.amount} colorize="balance" />,
    },
    {
      key: 'category',
      header: 'Category',
      render: (t) => <CategoryCell txn={t} categories={categories} onChange={changeCategory} />,
    },
    { key: 'account', header: 'Account', render: (t) => acctName[t.account_id] ?? t.account_id },
    {
      key: 'status',
      header: 'Status',
      render: (t) =>
        t.pending ? <Badge variant="warn">Pending</Badge> : <Badge>Settled</Badge>,
    },
    { key: 'source', header: 'Source', render: (t) => <span className="muted">{t.source}</span> },
  ];

  return (
    <div className="stack">
      <PageHeader
        title="Transactions"
        subtitle="Filterable history across all accounts"
        actions={
          txns.length > 0 ? (
            <div className="header-actions">
              {uncategorizedCount > 0 && (
                <button className="btn" onClick={runAutoCategorize} disabled={autocatting}>
                  {autocatting ? <Spinner /> : <Wand2 size={15} />}
                  Auto-categorize {uncategorizedCount}
                </button>
              )}
              <button className="btn" onClick={exportCsv}>
                <Download size={15} /> Export CSV
              </button>
            </div>
          ) : undefined
        }
      />

      {notice && (
        <div className="cat-notice" onAnimationEnd={() => setNotice('')}>
          {notice}
        </div>
      )}

      {/* Filters */}
      <Card>
        <div className="filters">
          <div className="field">
            <span className="field-label">Period</span>
            <select className="select" value={days} onChange={(e) => setDays(Number(e.target.value))}>
              {PERIODS.map((d) => (
                <option key={d} value={d}>
                  Last {d} days
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <span className="field-label">Account</span>
            <select className="select" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              <option value="">All accounts</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <span className="field-label">Category</span>
            <select className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div className="field grow">
            <span className="field-label">Search</span>
            <input
              className="input"
              placeholder="e.g. Amazon, Starbucks"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
      </Card>

      {txnsQ.loading ? (
        <Spinner center />
      ) : txnsQ.error ? (
        <div className="section-error">Couldn’t load transactions: {txnsQ.error}</div>
      ) : (
        <>
          {/* Summary */}
          <div className="grid metrics">
            <StatCard label="Transactions" value={txns.length} accent="accent" />
            <StatCard label="Total spent" value={<Money value={totalSpent} />} accent="warning" />
            <StatCard label="Credits / refunds" value={<Money value={totalCredit} />} accent="positive" />
            <StatCard label="Largest" value={<Money value={largest} />} accent="negative" />
          </div>

          {/* Charts */}
          <div className="grid two-col">
            <Card title="Spending by category">
              {byCategory.length > 0 ? (
                <BarCategory data={byCategory} height={280} />
              ) : (
                <div className="muted pad">No spending in this period.</div>
              )}
            </Card>
            <Card title="Spending over time">
              {overTime.length > 1 ? (
                <AreaTrend data={overTime} xKey="day" yKey="amount" height={280} color="var(--warning)" />
              ) : (
                <div className="muted pad">Not enough data to chart.</div>
              )}
            </Card>
          </div>

          {/* Table */}
          <Card title={`All transactions (${txns.length})`} flush>
            <DataTable
              columns={columns}
              rows={txns}
              rowKey={(t) => t.id}
              empty={{
                title: 'No transactions',
                hint: 'Try widening the period or clearing filters — or import a CSV.',
              }}
            />
          </Card>
        </>
      )}
    </div>
  );
}
