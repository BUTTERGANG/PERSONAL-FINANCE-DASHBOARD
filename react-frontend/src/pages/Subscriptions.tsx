import { EyeOff, Repeat } from 'lucide-react';
import { fetchSubscriptions, ignoreSubscription } from '../services/api';
import { useAsync } from '../hooks/useAsync';
import type { Subscription } from '../services/types';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import StatCard from '../components/StatCard';
import Money, { formatMoney } from '../components/Money';
import Badge from '../components/Badge';
import Spinner from '../components/Spinner';
import EmptyState from '../components/EmptyState';
import './Subscriptions.css';

function titleCase(s: string): string {
  return s.replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());
}

export default function Subscriptions() {
  const subsQ = useAsync<Subscription[]>(fetchSubscriptions);
  const subs = subsQ.data ?? [];

  async function hide(key: string) {
    await ignoreSubscription(key);
    subsQ.reload();
  }

  const totalMonthly = subs.reduce((s, x) => s + x.monthly_cost, 0);
  const totalAnnual = subs.reduce((s, x) => s + x.est_annual, 0);

  return (
    <div className="stack">
      <PageHeader
        title="Subscriptions"
        subtitle="Recurring charges detected from the last 180 days — hide anything that isn’t a real subscription"
      />

      {subsQ.loading ? (
        <Spinner center />
      ) : subsQ.error ? (
        <div className="section-error">Couldn’t load subscriptions: {subsQ.error}</div>
      ) : subs.length === 0 ? (
        <Card>
          <EmptyState
            title="No recurring charges detected"
            hint="This fills in once a few months of transactions are synced or imported."
          />
        </Card>
      ) : (
        <>
          <div className="grid metrics3">
            <StatCard label="Active subscriptions" value={subs.length} accent="accent" />
            <StatCard label="Est. monthly cost" value={<Money value={totalMonthly} />} accent="warning" />
            <StatCard label="Est. annual cost" value={<Money value={totalAnnual} />} accent="negative" />
          </div>

          <Card title="Detected subscriptions" flush>
            <div className="sub-list">
              {subs.map((s) => (
                <div key={s.merchant_key} className="sub-row">
                  <span className="sub-icon">
                    <Repeat size={16} />
                  </span>
                  <div className="sub-info">
                    <div className="sub-merchant">
                      {titleCase(s.merchant)}
                      <Badge>{s.frequency}</Badge>
                    </div>
                    <div className="sub-meta">
                      {s.category} · seen {s.occurrences}× · last {s.last_date}
                    </div>
                  </div>
                  <div className="sub-cost">
                    <div className="sub-amount tnum">{formatMoney(s.amount)}</div>
                    <div className="sub-annual">
                      ~{formatMoney(s.monthly_cost)}/mo · {formatMoney(s.est_annual)}/yr
                    </div>
                  </div>
                  <button
                    className="btn btn-sm sub-hide"
                    onClick={() => hide(s.merchant_key)}
                    title="Not a subscription — hide it"
                  >
                    <EyeOff size={14} /> Hide
                  </button>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
