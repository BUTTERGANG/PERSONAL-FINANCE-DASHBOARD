import { useState } from 'react';
import { RefreshCw, CheckCircle2, XCircle, Landmark } from 'lucide-react';
import { fetchAccounts, fetchSyncLogs, triggerSync } from '../services/api';
import { useAsync } from '../hooks/useAsync';
import type { Account, SyncLog } from '../services/types';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Money from '../components/Money';
import Badge from '../components/Badge';
import Spinner from '../components/Spinner';
import EmptyState from '../components/EmptyState';
import './Accounts.css';

const CREDIT_TYPES = new Set(['credit', 'loan']);

const INST_FULL: Record<string, string> = {
  chase: 'JPMorgan Chase',
  citi: 'Citibank',
  fidelity: 'Fidelity',
  paypal: 'PayPal',
  venmo: 'Venmo',
  manual: 'Manual',
};

function fullName(institution: string): string {
  const key = institution.split(/[-_]/)[0].toLowerCase();
  return INST_FULL[key] ?? institution;
}

function formatSynced(iso: string | null): string {
  if (!iso) return 'Never synced';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return 'Never synced';
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export default function Accounts() {
  const accountsQ = useAsync<Account[]>(fetchAccounts);
  const logsQ = useAsync<SyncLog[]>(() => fetchSyncLogs(10));
  const [syncing, setSyncing] = useState(false);
  const [toast, setToast] = useState('');

  async function sync() {
    setSyncing(true);
    setToast('');
    try {
      await triggerSync();
      setToast('Sync started — balances refresh in the background.');
      accountsQ.reload();
      logsQ.reload();
    } catch {
      setToast('Sync failed — is the backend running?');
    } finally {
      setSyncing(false);
      setTimeout(() => setToast(''), 4000);
    }
  }

  if (accountsQ.loading) return <Spinner center />;
  if (accountsQ.error)
    return <div className="section-error">Couldn’t load accounts: {accountsQ.error}</div>;

  const accounts = accountsQ.data ?? [];
  const logs = logsQ.data ?? [];

  return (
    <div className="stack">
      <PageHeader
        title="Accounts"
        subtitle="Balances and sync status by institution"
        actions={
          <button className="btn btn-primary" onClick={sync} disabled={syncing}>
            <RefreshCw size={15} className={syncing ? 'spin-icon' : ''} />
            {syncing ? 'Syncing…' : 'Sync all now'}
          </button>
        }
      />

      {toast && <div className="toast-inline">{toast}</div>}

      {accounts.length === 0 ? (
        <Card>
          <EmptyState
            title="No accounts linked yet"
            hint="Link a bank on the Link account page, or add a manual account on Import."
          />
        </Card>
      ) : (
        <div className="account-cards">
          {accounts.map((a) => {
            const isCredit = CREDIT_TYPES.has(a.account_type);
            return (
              <Card key={a.id}>
                <div className="acct-card">
                  <div className="acct-main">
                    <span className="acct-icon">
                      <Landmark size={18} />
                    </span>
                    <div>
                      <div className="acct-name">{a.name}</div>
                      <div className="acct-meta">
                        {fullName(a.institution)} · {a.account_type} · {a.currency}
                      </div>
                      <div className="acct-synced">Last synced: {formatSynced(a.last_synced)}</div>
                    </div>
                  </div>
                  <div className="acct-balance">
                    <div className="acct-balance-label">
                      {isCredit ? 'Amount owed' : 'Current balance'}
                    </div>
                    <div className="acct-balance-value">
                      <Money value={isCredit ? -a.balance : a.balance} colorize="balance" />
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <Card title="Recent sync activity">
        {logsQ.loading ? (
          <Spinner center />
        ) : logs.length === 0 ? (
          <EmptyState title="No sync history yet" hint="Runs appear here after the first sync." />
        ) : (
          <div className="sync-log">
            {logs.map((log) => {
              const ok = log.status === 'success';
              return (
                <div key={log.id} className="sync-row">
                  <span className={ok ? 'ok' : 'err'}>
                    {ok ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                  </span>
                  <span className="sync-inst">{fullName(log.institution)}</span>
                  <span className="sync-detail">
                    {ok
                      ? `${log.transactions_added} new transaction${log.transactions_added === 1 ? '' : 's'}`
                      : log.error_message || 'Error'}
                  </span>
                  <span className="sync-time">{formatSynced(log.synced_at)}</span>
                  {!ok && <Badge variant="neg">failed</Badge>}
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
