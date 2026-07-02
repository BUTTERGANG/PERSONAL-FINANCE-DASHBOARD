import { AlertTriangle, TrendingUp } from 'lucide-react';
import {
  fetchAccounts,
  fetchTransactions,
  fetchMonthOverMonth,
  fetchBudgetAlerts,
  fetchNetWorthSnapshots,
} from '../services/api';
import { useAsync } from '../hooks/useAsync';
import type { Account, Transaction, MonthOverMonth, BudgetAlert, NetWorthSnapshot } from '../services/types';
import Card from '../components/Card';
import StatCard from '../components/StatCard';
import Money, { formatMoney } from '../components/Money';
import Spinner from '../components/Spinner';
import EmptyState from '../components/EmptyState';
import Badge from '../components/Badge';
import AreaTrend from '../components/charts/AreaTrend';
import './Overview.css';

const CREDIT_TYPES = new Set(['credit', 'loan']);

export default function Overview() {
  const accountsQ = useAsync<Account[]>(fetchAccounts);
  const txnsQ = useAsync<Transaction[]>(() => fetchTransactions({ days: 30 }));
  const momQ = useAsync<MonthOverMonth>(fetchMonthOverMonth);
  const alertsQ = useAsync<BudgetAlert[]>(fetchBudgetAlerts);
  const snapshotsQ = useAsync<NetWorthSnapshot[]>(() => fetchNetWorthSnapshots(180));

  if (accountsQ.loading) return <Spinner center />;
  if (accountsQ.error) return <div className="section-error">Couldn’t load data: {accountsQ.error}</div>;

  const accounts = accountsQ.data ?? [];
  const txns = txnsQ.data ?? [];
  const mom = momQ.data;
  const alerts = alertsQ.data ?? [];
  const snapshots = snapshotsQ.data ?? [];

  const assets = accounts.filter((a) => !CREDIT_TYPES.has(a.account_type)).reduce((s, a) => s + a.balance, 0);
  const debt = accounts.filter((a) => CREDIT_TYPES.has(a.account_type)).reduce((s, a) => s + a.balance, 0);
  const netWorth = assets - debt;
  const spent30 = txns.filter((t) => t.amount > 0 && !t.pending).reduce((s, t) => s + t.amount, 0);

  const trendData = snapshots.map((s) => ({ day: s.day.slice(5), net_worth: s.net_worth }));

  // top MoM movers (biggest absolute change), max 4
  const movers = (mom?.categories ?? [])
    .filter((c) => c.pct_change !== null)
    .sort((a, b) => Math.abs(b.this_month - b.last_month_same_point) - Math.abs(a.this_month - a.last_month_same_point))
    .slice(0, 4);

  return (
    <div className="stack">
      {/* Budget alerts */}
      {alerts.length > 0 && (
        <div className="alerts">
          {alerts.map((a) => (
            <div key={a.category} className={`alert alert-${a.level}`}>
              <AlertTriangle size={16} />
              <span>
                <strong>{a.category}</strong> — {a.message}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Key metrics */}
      <div className="grid metrics">
        <StatCard label="Net worth" accent="accent" value={<Money value={netWorth} />} />
        <StatCard label="Assets" accent="positive" value={<Money value={assets} />} />
        <StatCard label="Debt" accent="negative" value={<Money value={debt} />} />
        <StatCard label="Spent (30d)" accent="warning" value={<Money value={spent30} />} />
      </div>

      {/* Net worth trend */}
      <Card
        title="Net worth trend"
        action={
          snapshots.length > 1 ? (
            <Badge variant="accent">
              <TrendingUp size={13} /> {snapshots.length} days
            </Badge>
          ) : undefined
        }
      >
        {snapshotsQ.loading ? (
          <Spinner center />
        ) : trendData.length > 1 ? (
          <AreaTrend data={trendData} xKey="day" yKey="net_worth" />
        ) : (
          <EmptyState
            title="Not enough history yet"
            hint="Net worth is snapshotted once a day. Check back after a few syncs."
          />
        )}
      </Card>

      <div className="grid two-col">
        {/* Month over month movers */}
        <Card title="This month vs last">
          {movers.length > 0 ? (
            <div className="movers">
              {movers.map((c) => {
                const up = (c.pct_change ?? 0) > 0;
                return (
                  <div key={c.category} className="mover">
                    <div className="mover-cat">{c.category}</div>
                    <div className="mover-amt tnum">{formatMoney(c.this_month)}</div>
                    <Badge variant={up ? 'neg' : 'pos'}>
                      {up ? '▲' : '▼'} {Math.abs(c.pct_change ?? 0)}%
                    </Badge>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState title="No comparison yet" hint="Spending trends appear once you have two months of data." />
          )}
        </Card>

        {/* Accounts */}
        <Card title="Accounts" action={<span className="muted-count">{accounts.length}</span>}>
          {accounts.length > 0 ? (
            <div className="accounts-list">
              {accounts.map((a) => {
                const isCredit = CREDIT_TYPES.has(a.account_type);
                return (
                  <div key={a.id} className="account-row">
                    <div>
                      <div className="account-name">{a.name}</div>
                      <div className="account-meta">
                        {a.institution} · {a.account_type}
                      </div>
                    </div>
                    <Money value={isCredit ? -a.balance : a.balance} colorize="balance" />
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState title="No accounts linked" hint="Link an account or add one manually to get started." />
          )}
        </Card>
      </div>
    </div>
  );
}
