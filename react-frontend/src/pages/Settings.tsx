import { useState } from 'react';
import { Zap, Download, CheckCircle2, XCircle } from 'lucide-react';
import {
  fetchHealth,
  fetchAccounts,
  fetchSyncLogs,
  fetchTransactions,
  triggerSyncRealtime,
} from '../services/api';
import { useAsync } from '../hooks/useAsync';
import type { Health, Account, SyncLog } from '../services/types';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Spinner from '../components/Spinner';
import DataTable, { type Column } from '../components/DataTable';
import './Settings.css';

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

async function downloadTxnCsv(days: number) {
  const txns = await fetchTransactions({ days });
  if (!txns.length) {
    alert('No transactions to export.');
    return;
  }
  const header = ['id', 'date', 'description', 'amount', 'category', 'account_id', 'pending', 'source'];
  const lines = txns.map((t) =>
    [
      t.id,
      t.date.slice(0, 10),
      `"${t.description.replace(/"/g, '""')}"`,
      t.amount.toFixed(2),
      t.category ?? '',
      t.account_id,
      t.pending,
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

export default function Settings() {
  const healthQ = useAsync<Health | null>(fetchHealth);
  const accountsQ = useAsync<Account[]>(fetchAccounts);
  const logsQ = useAsync<SyncLog[]>(() => fetchSyncLogs(20));

  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState('');

  const health = healthQ.data;
  const accounts = accountsQ.data ?? [];
  const logs = logsQ.data ?? [];
  const institutions = new Set(accounts.map((a) => a.institution));

  async function liveSync() {
    setSyncing(true);
    setSyncMsg('');
    try {
      const res = await triggerSyncRealtime();
      setSyncMsg(
        (res as { status?: string }).status === 'completed'
          ? 'Live sync complete — balances are current as of now.'
          : 'Sync request sent.',
      );
      logsQ.reload();
      accountsQ.reload();
    } catch (e) {
      setSyncMsg(e instanceof Error ? `Sync failed: ${e.message}` : 'Sync failed.');
    } finally {
      setSyncing(false);
    }
  }

  const logColumns: Column<SyncLog>[] = [
    { key: 'synced_at', header: 'Time', sortable: true, sortValue: (l) => l.synced_at, render: (l) => formatTime(l.synced_at) },
    { key: 'institution', header: 'Institution', render: (l) => l.institution },
    {
      key: 'status',
      header: 'Status',
      render: (l) =>
        l.status === 'success' ? (
          <span className="ok"><CheckCircle2 size={14} /> success</span>
        ) : (
          <span className="err"><XCircle size={14} /> error</span>
        ),
    },
    { key: 'added', header: 'Added', numeric: true, sortable: true, sortValue: (l) => l.transactions_added, render: (l) => l.transactions_added },
    { key: 'error', header: 'Detail', render: (l) => l.error_message ?? <span className="muted">—</span> },
  ];

  return (
    <div className="stack">
      <PageHeader title="Settings" subtitle="Sync configuration, data export, and system status" />

      {/* System status */}
      <Card title="System status">
        {healthQ.loading ? (
          <Spinner center />
        ) : health ? (
          <div className="status-row">
            <Badge variant="pos">
              <CheckCircle2 size={13} /> Backend healthy
            </Badge>
            <span className="muted">
              Sync interval: every {health.sync_interval_hours} hours ·{' '}
              {accounts.length} account{accounts.length === 1 ? '' : 's'} across{' '}
              {institutions.size} institution{institutions.size === 1 ? '' : 's'}
            </span>
          </div>
        ) : (
          <Badge variant="neg">
            <XCircle size={13} /> Backend not responding
          </Badge>
        )}
      </Card>

      {/* Sync */}
      <Card title="Sync">
        <p className="muted">
          The interval is set via the <code>SYNC_INTERVAL_HOURS</code> environment variable (default
          4 hours). Trigger a live balance sync on demand below.
        </p>
        <button className="btn btn-primary" onClick={liveSync} disabled={syncing}>
          {syncing ? <Spinner /> : <Zap size={15} />}
          {syncing ? 'Syncing live balances…' : 'Sync now (live balances)'}
        </button>
        {syncMsg && <div className="sync-msg">{syncMsg}</div>}
      </Card>

      {/* Export */}
      <Card title="Export data">
        <p className="muted">Download your transaction history as CSV.</p>
        <div className="export-actions">
          <button className="btn" onClick={() => downloadTxnCsv(30)}>
            <Download size={15} /> Last 30 days
          </button>
          <button className="btn" onClick={() => downloadTxnCsv(365)}>
            <Download size={15} /> Last 365 days
          </button>
        </div>
      </Card>

      {/* Sync history */}
      <Card title="Sync history" flush>
        {logsQ.loading ? (
          <Spinner center />
        ) : (
          <DataTable
            columns={logColumns}
            rows={logs}
            rowKey={(l) => String(l.id)}
            empty={{ title: 'No sync history yet' }}
          />
        )}
      </Card>

      {/* About */}
      <Card title="About">
        <p className="muted">
          Personal Finance Dashboard — FastAPI + React + Plaid + OFX. Docs live in{' '}
          <code>THE-VISION/</code>: architecture, security model, and roadmap.
        </p>
      </Card>
    </div>
  );
}
