import { Trash2 } from 'lucide-react';
import { fetchPortfolio, deleteHolding } from '../services/api';
import { useAsync } from '../hooks/useAsync';
import type { PortfolioResponse, StoredHolding } from '../services/types';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import StatCard from '../components/StatCard';
import Money, { formatMoney } from '../components/Money';
import Badge from '../components/Badge';
import Spinner from '../components/Spinner';
import EmptyState from '../components/EmptyState';
import './Portfolio.css';

function fmtQty(q: number | null): string {
  if (q == null) return '—';
  // Crypto sizes need many decimals; equities read better trimmed.
  return q.toLocaleString('en-US', { maximumFractionDigits: 8 });
}

function pctLabel(p: number | null): string | undefined {
  if (p == null) return undefined;
  return `${p >= 0 ? '+' : ''}${p.toFixed(2)}%`;
}

export default function Portfolio() {
  const q = useAsync<PortfolioResponse>(() => fetchPortfolio(), []);
  const data = q.data;

  async function remove(h: StoredHolding) {
    await deleteHolding(h.id);
    q.reload();
  }

  return (
    <div className="stack">
      <PageHeader
        title="Portfolio"
        subtitle="Investment positions persisted from brokerage statements"
      />

      {q.loading && <Spinner />}
      {q.error && <EmptyState title="Couldn't load the portfolio" hint={q.error} />}

      {!q.loading && data && data.totals.positions === 0 && (
        <Card>
          <EmptyState
            title="No positions yet"
            hint="Import a Fidelity brokerage or crypto statement on the Import page — its holdings are saved here automatically."
          />
        </Card>
      )}

      {!q.loading && data && data.totals.positions > 0 && (
        <>
          <div className="portfolio-stats">
            <StatCard
              label="Market value"
              value={formatMoney(data.totals.market_value)}
              accent="accent"
            />
            <StatCard
              label="Cost basis"
              value={formatMoney(data.totals.cost_basis)}
              accent="accent"
            />
            <StatCard
              label="Unrealized gain"
              value={
                <Money
                  value={data.totals.unrealized_gain}
                  colorize="balance"
                  signed
                />
              }
              accent={data.totals.unrealized_gain >= 0 ? 'positive' : 'negative'}
              delta={
                data.totals.return_pct != null
                  ? {
                      text: pctLabel(data.totals.return_pct)!,
                      direction:
                        data.totals.return_pct > 0
                          ? 'up'
                          : data.totals.return_pct < 0
                            ? 'down'
                            : 'flat',
                    }
                  : undefined
              }
              deltaGood="up"
            />
          </div>

          {data.accounts.map((acct) => (
            <Card
              key={acct.account_id}
              title={acct.account_name}
              action={
                <div className="portfolio-acct-badges">
                  <Badge variant="accent">{acct.positions} positions</Badge>
                  <Badge variant={acct.unrealized_gain >= 0 ? 'pos' : 'neg'}>
                    <Money value={acct.unrealized_gain} signed />
                  </Badge>
                </div>
              }
              flush
            >
              <div className="table-wrap">
                <table className="portfolio-table">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Description</th>
                      <th className="num">Quantity</th>
                      <th className="num">Price</th>
                      <th className="num">Market value</th>
                      <th className="num">Cost basis</th>
                      <th className="num">Unrealized</th>
                      <th className="actions-col" aria-label="Actions" />
                    </tr>
                  </thead>
                  <tbody>
                    {acct.holdings.map((h) => (
                      <tr key={h.id}>
                        <td>
                          <strong>{h.symbol ?? '—'}</strong>
                        </td>
                        <td>
                          <span className="portfolio-desc">{h.description}</span>
                          {h.as_of && (
                            <span className="portfolio-asof">statement {h.as_of}</span>
                          )}
                        </td>
                        <td className="num tnum">{fmtQty(h.quantity)}</td>
                        <td className="num tnum">
                          {h.price != null ? formatMoney(h.price) : '—'}
                        </td>
                        <td className="num tnum">
                          {h.market_value != null ? formatMoney(h.market_value) : '—'}
                        </td>
                        <td className="num tnum">
                          {h.cost_basis != null ? formatMoney(h.cost_basis) : '—'}
                        </td>
                        <td className="num tnum">
                          {h.unrealized_gain != null ? (
                            <Money value={h.unrealized_gain} colorize="balance" signed />
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="actions-col">
                          <button
                            className="icon-btn danger"
                            onClick={() => remove(h)}
                            aria-label={`Remove ${h.symbol ?? h.description}`}
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    ))}
                    <tr className="portfolio-total-row">
                      <td colSpan={4}>Total</td>
                      <td className="num tnum">{formatMoney(acct.market_value)}</td>
                      <td className="num tnum">
                        {acct.cost_basis ? formatMoney(acct.cost_basis) : '—'}
                      </td>
                      <td className="num tnum">
                        <Money value={acct.unrealized_gain} colorize="balance" signed />
                      </td>
                      <td />
                    </tr>
                  </tbody>
                </table>
              </div>
            </Card>
          ))}

          <p className="portfolio-note">
            Positions come from imported statements and update in place when you re-import a
            later statement for the same account — no duplicates. Re-import each month to keep
            values current.
          </p>
        </>
      )}
    </div>
  );
}
