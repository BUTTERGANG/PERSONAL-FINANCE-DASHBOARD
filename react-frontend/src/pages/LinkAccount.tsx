import { useState } from 'react';
import { ExternalLink, RefreshCw, CheckCircle2, Circle, ChevronDown } from 'lucide-react';
import { fetchAccounts, plaidLinkUrl } from '../services/api';
import { useAsync } from '../hooks/useAsync';
import type { Account } from '../services/types';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Spinner from '../components/Spinner';
import './LinkAccount.css';

const PLAID_INSTITUTIONS = [
  { key: 'chase', name: 'Chase', type: 'Checking / Savings' },
  { key: 'citi', name: 'Citi', type: 'Credit Card' },
  { key: 'paypal', name: 'PayPal', type: 'Digital Wallet' },
  { key: 'venmo', name: 'Venmo', type: 'Digital Wallet' },
];

export default function LinkAccount() {
  const accountsQ = useAsync<Account[]>(fetchAccounts);
  const [showFidelity, setShowFidelity] = useState(false);

  const accounts = accountsQ.data ?? [];
  const linked = new Set(accounts.map((a) => a.institution.split(/[-_]/)[0].toLowerCase()));
  const fidelityLinked = linked.has('fidelity');

  return (
    <div className="stack">
      <PageHeader
        title="Link account"
        subtitle="Connect your financial accounts — you only do this once per institution"
      />

      <Card title="Connect via Plaid">
        <p className="muted">
          Plaid handles authentication and 2FA. Your bank credentials never touch this server.
        </p>

        <div className="inst-grid">
          {PLAID_INSTITUTIONS.map((inst) => {
            const isLinked = linked.has(inst.key);
            return (
              <div key={inst.key} className={`inst-card${isLinked ? ' linked' : ''}`}>
                <div className="inst-name">{inst.name}</div>
                <div className="inst-type">{inst.type}</div>
                <div className={`inst-status ${isLinked ? 'on' : 'off'}`}>
                  {isLinked ? <CheckCircle2 size={14} /> : <Circle size={14} />}
                  {isLinked ? 'Connected' : 'Not linked'}
                </div>
              </div>
            );
          })}
        </div>

        <p className="muted small">
          Open Plaid Link, choose your institution, complete authentication, then come back and
          refresh.
        </p>
        <div className="link-actions">
          <a className="btn btn-primary" href={plaidLinkUrl()} target="_blank" rel="noreferrer">
            <ExternalLink size={15} /> Open Plaid Link
          </a>
          <button className="btn" onClick={() => accountsQ.reload()} disabled={accountsQ.loading}>
            <RefreshCw size={15} className={accountsQ.loading ? 'spin-icon' : ''} /> Refresh accounts
          </button>
        </div>
      </Card>

      <Card
        title="Fidelity (investments)"
        action={
          <Badge variant={fidelityLinked ? 'pos' : 'warn'}>
            {fidelityLinked ? 'Connected' : 'Not configured'}
          </Badge>
        }
      >
        <p className="muted">
          Fidelity connects via <strong>OFX Direct Connect</strong> — the same protocol Quicken
          uses. No Plaid Link, no 2FA per pull. Configured once via environment secrets.
        </p>

        {!fidelityLinked && (
          <div className="disclosure">
            <button className="disclosure-toggle" onClick={() => setShowFidelity((v) => !v)}>
              <ChevronDown size={15} className={showFidelity ? 'rot' : ''} />
              How to set up Fidelity OFX
            </button>
            {showFidelity && (
              <div className="disclosure-body">
                <p>
                  <strong>1.</strong> Set these in your environment / Replit Secrets:
                </p>
                <ul>
                  <li>
                    <code>FIDELITY_USER</code> — your Fidelity username
                  </li>
                  <li>
                    <code>FIDELITY_PIN</code> — password or a separate Direct Connect PIN
                  </li>
                  <li>
                    <code>FIDELITY_ACCOUNT_ID</code> — your 9-digit account number
                  </li>
                </ul>
                <p>
                  <strong>2.</strong> Restart the app so the new secrets load.
                </p>
                <p>
                  <strong>3.</strong> Click <em>Sync all now</em> on the Accounts page — Fidelity
                  appears in the sync logs when configured.
                </p>
                <p className="muted small">
                  If it fails with an auth error, call Fidelity at 800-343-3548 and ask to enable
                  “Quicken Direct Connect.” See THE-VISION/SECURITY.md → Troubleshooting Fidelity OFX.
                </p>
              </div>
            )}
          </div>
        )}
      </Card>

      <Card title="Currently linked accounts">
        {accountsQ.loading ? (
          <Spinner center />
        ) : accounts.length === 0 ? (
          <p className="muted">Nothing linked yet.</p>
        ) : (
          <ul className="linked-list">
            {accounts.map((a) => (
              <li key={a.id}>
                <strong>{a.name}</strong>
                <span className="muted">
                  {' '}
                  · {a.institution} · {a.account_type}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
