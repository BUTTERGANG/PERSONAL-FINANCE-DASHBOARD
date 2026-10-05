import { useState } from 'react';
import { ChevronLeft, ChevronRight, Pencil, Plus, Trash2, X } from 'lucide-react';
import {
  fetchCarry,
  fetchPayoff,
  addCarryItem,
  updateCarryItem,
  deleteCarryItem,
} from '../services/api';
import { useAsync } from '../hooks/useAsync';
import type { CarryItemRow, CarrySummary, PayoffResponse } from '../services/types';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Money, { formatMoney } from '../components/Money';
import Spinner from '../components/Spinner';
import EmptyState from '../components/EmptyState';
import './Carry.css';

function shiftMonth(ym: string, delta: number): string {
  const [y, m] = ym.split('-').map(Number);
  const d = new Date(Date.UTC(y, m - 1 + delta, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

function monthLabel(ym: string): string {
  const [y, m] = ym.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

function rangeLabel(low: number, high: number): string {
  return low === high ? formatMoney(low) : `${formatMoney(low)}–${formatMoney(high)}`;
}

interface Draft {
  id: number | null;
  name: string;
  group: string;
  low: string;
  high: string;
  keywords: string;
  is_debt: boolean;
  balance: string;
  apr: string;
  min_payment: string;
}

const emptyDraft: Draft = {
  id: null,
  name: '',
  group: 'Software',
  low: '',
  high: '',
  keywords: '',
  is_debt: false,
  balance: '',
  apr: '',
  min_payment: '',
};

export default function Carry() {
  const [month, setMonth] = useState<string>(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });
  const q = useAsync<CarrySummary>(() => fetchCarry(month), [month]);
  const [extra, setExtra] = useState('');
  const payoffQ = useAsync<PayoffResponse>(
    () => fetchPayoff(parseFloat(extra) > 0 ? parseFloat(extra) : undefined),
    [extra, q.data ? 1 : 0],
  );

  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');

  const summary = q.data;
  const totals = summary?.totals;
  const actualVsHigh = totals ? totals.monthly_actual - totals.monthly_high : 0;

  function startEdit(item: CarryItemRow) {
    setDraft({
      id: item.id,
      name: item.name,
      group: item.group,
      low: String(item.monthly_low),
      high: item.monthly_high !== item.monthly_low ? String(item.monthly_high) : '',
      keywords: item.merchant_keywords,
      is_debt: item.is_debt,
      balance: item.balance != null ? String(item.balance) : '',
      apr: item.apr != null ? String(item.apr) : '',
      min_payment: item.min_payment != null ? String(item.min_payment) : '',
    });
    setErr('');
  }

  async function saveDraft() {
    if (!draft) return;
    const low = parseFloat(draft.low);
    if (!draft.name.trim() || isNaN(low) || low <= 0) {
      setErr('Enter a name and a monthly amount greater than 0.');
      return;
    }
    const highRaw = parseFloat(draft.high);
    const high = !isNaN(highRaw) && highRaw > low ? highRaw : null;
    const balance = parseFloat(draft.balance);
    const apr = parseFloat(draft.apr);
    const minPay = parseFloat(draft.min_payment);
    setSaving(true);
    setErr('');
    const debtFields = draft.is_debt
      ? {
          is_debt: true,
          balance: !isNaN(balance) ? balance : null,
          apr: !isNaN(apr) ? apr : null,
          min_payment: !isNaN(minPay) ? minPay : null,
        }
      : { is_debt: false, balance: null, apr: null, min_payment: null };
    try {
      if (draft.id) {
        await updateCarryItem(draft.id, {
          name: draft.name.trim(),
          group: draft.group,
          monthly_low: low,
          monthly_high: high,
          merchant_keywords: draft.keywords.trim() || null,
          ...debtFields,
        });
      } else {
        await addCarryItem({
          name: draft.name.trim(),
          group: draft.group,
          monthly_low: low,
          monthly_high: high,
          merchant_keywords: draft.keywords.trim() || null,
          category: null,
          sort_order: 500,
          ...debtFields,
        });
      }
      setDraft(null);
      q.reload();
      payoffQ.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Could not save the item.');
    } finally {
      setSaving(false);
    }
  }

  async function remove(item: CarryItemRow) {
    await deleteCarryItem(item.id);
    q.reload();
  }

  const nowYm = (() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  })();

  return (
    <div className="stack">
      <PageHeader
        title="Monthly Carry"
        subtitle="Recurring obligations — fixed estimates vs. what statements show"
        actions={
          <div className="carry-month-nav">
            <button className="icon-btn" onClick={() => setMonth((m) => shiftMonth(m, -1))} aria-label="Previous month">
              <ChevronLeft size={16} />
            </button>
            <span className="carry-month-label">{monthLabel(month)}</span>
            <button
              className="icon-btn"
              onClick={() => setMonth((m) => shiftMonth(m, 1))}
              disabled={month >= nowYm}
              aria-label="Next month"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        }
      />

      {q.loading && <Spinner />}
      {q.error && <EmptyState title="Couldn't load the carry" hint={q.error} />}
      {!q.loading && summary && totals && (
        <>
          <div className="carry-stats">
            <Card className="carry-stat">
              <span className="carry-stat-label">Monthly carry</span>
              <span className="carry-stat-value tnum">{rangeLabel(totals.monthly_low, totals.monthly_high)}</span>
              <span className="carry-stat-sub">fixed estimates</span>
            </Card>
            <Card className="carry-stat">
              <span className="carry-stat-label">This month actual</span>
              <span className="carry-stat-value tnum">{formatMoney(totals.monthly_actual)}</span>
              <span className={`carry-stat-sub ${actualVsHigh > 0 ? 'neg' : 'pos'}`}>
                {actualVsHigh > 0 ? '+' : ''}
                {formatMoney(actualVsHigh)} vs. fixed high
              </span>
            </Card>
            <Card className="carry-stat">
              <span className="carry-stat-label">
                {totals.quarter_months}-month total
              </span>
              <span className="carry-stat-value tnum">
                {rangeLabel(totals.quarter_low, totals.quarter_high)}
              </span>
              <span className="carry-stat-sub">fixed carry × {totals.quarter_months}</span>
            </Card>
          </div>

          <Card
            title="Line items"
            action={
              !draft ? (
                <button className="btn btn-sm" onClick={() => setDraft(emptyDraft)}>
                  <Plus size={14} /> Add item
                </button>
              ) : undefined
            }
          >
            {draft && (
              <div className="carry-editor">
                <div className="carry-editor-grid">
                  <label className="field">
                    <span className="field-label">Name</span>
                    <input
                      className="input"
                      value={draft.name}
                      onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                      placeholder="e.g. Spotify"
                    />
                  </label>
                  <label className="field">
                    <span className="field-label">Group</span>
                    <select
                      className="select"
                      value={draft.group}
                      onChange={(e) => setDraft({ ...draft, group: e.target.value })}
                    >
                      {['Credit Cards', 'Transport', 'Insurance', 'Software', 'Bills', 'Other'].map((g) => (
                        <option key={g} value={g}>
                          {g}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span className="field-label">Monthly low ($)</span>
                    <input
                      className="input"
                      inputMode="decimal"
                      value={draft.low}
                      onChange={(e) => setDraft({ ...draft, low: e.target.value })}
                      placeholder="25.00"
                    />
                  </label>
                  <label className="field">
                    <span className="field-label">Monthly high ($) — ranges only</span>
                    <input
                      className="input"
                      inputMode="decimal"
                      value={draft.high}
                      onChange={(e) => setDraft({ ...draft, high: e.target.value })}
                      placeholder="optional"
                    />
                  </label>
                  <label className="field grow">
                    <span className="field-label">Merchant keywords (comma-separated)</span>
                    <input
                      className="input"
                      value={draft.keywords}
                      onChange={(e) => setDraft({ ...draft, keywords: e.target.value })}
                      placeholder="e.g. spotify, netflix"
                    />
                  </label>
                  <label className="field grow carry-debt-toggle">
                    <span className="field-label">Type</span>
                    <select
                      className="select"
                      value={draft.is_debt ? 'debt' : 'expense'}
                      onChange={(e) => setDraft({ ...draft, is_debt: e.target.value === 'debt' })}
                    >
                      <option value="expense">Expense (no balance)</option>
                      <option value="debt">Debt (balance + APR)</option>
                    </select>
                  </label>
                  {draft.is_debt && (
                    <>
                      <label className="field">
                        <span className="field-label">Balance ($)</span>
                        <input
                          className="input"
                          inputMode="decimal"
                          value={draft.balance}
                          onChange={(e) => setDraft({ ...draft, balance: e.target.value })}
                          placeholder="from statement"
                        />
                      </label>
                      <label className="field">
                        <span className="field-label">APR (%) — off the invoice</span>
                        <input
                          className="input"
                          inputMode="decimal"
                          value={draft.apr}
                          onChange={(e) => setDraft({ ...draft, apr: e.target.value })}
                          placeholder="e.g. 22.25"
                        />
                      </label>
                      <label className="field">
                        <span className="field-label">Monthly payment ($)</span>
                        <input
                          className="input"
                          inputMode="decimal"
                          value={draft.min_payment}
                          onChange={(e) => setDraft({ ...draft, min_payment: e.target.value })}
                          placeholder="what you pay each month"
                        />
                      </label>
                    </>
                  )}
                </div>
                {err && <p className="form-error">{err}</p>}
                <div className="carry-editor-actions">
                  <button className="btn btn-sm" onClick={saveDraft} disabled={saving}>
                    {saving ? 'Saving…' : 'Save'}
                  </button>
                  <button className="btn btn-sm btn-ghost" onClick={() => setDraft(null)}>
                    <X size={14} /> Cancel
                  </button>
                </div>
              </div>
            )}

            <div className="table-wrap">
              <table className="carry-table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th className="num">Fixed / month</th>
                    <th className="num">Actual</th>
                    <th className="num">Δ</th>
                    <th className="actions-col" aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {summary.items.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <span className="carry-item-name">
                          {item.name}
                          {item.is_debt && <span className="carry-debt-badge">debt</span>}
                        </span>
                        <span className="carry-item-group">{item.group}</span>
                      </td>
                      <td className="num tnum">{rangeLabel(item.monthly_low, item.monthly_high)}</td>
                      <td className="num tnum">{item.actual > 0 ? formatMoney(item.actual) : '—'}</td>
                      <td className="num tnum">
                        {item.actual > 0 ? (
                          <span className={item.variance > 0 ? 'carry-delta neg' : 'carry-delta pos'}>
                            {item.variance > 0 ? '+' : ''}
                            {formatMoney(item.variance)}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="actions-col">
                        <button className="icon-btn" onClick={() => startEdit(item)} aria-label={`Edit ${item.name}`}>
                          <Pencil size={14} />
                        </button>
                        <button className="icon-btn danger" onClick={() => remove(item)} aria-label={`Delete ${item.name}`}>
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                  <tr className="carry-total-row">
                    <td>Total</td>
                    <td className="num tnum">
                      <Money value={totals.monthly_low} />
                      {totals.monthly_high !== totals.monthly_low && (
                        <>–<Money value={totals.monthly_high} /></>
                      )}
                    </td>
                    <td className="num tnum">{formatMoney(totals.monthly_actual)}</td>
                    <td className="num tnum">{formatMoney(actualVsHigh)}</td>
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="carry-note">
              Actuals come from imported statements (Import page) matched by merchant keywords.
              Items with no matching transactions this month show no actual yet.
            </p>
          </Card>

          <Card title="Debt payoff calculator">
            {payoffQ.loading && <Spinner />}
            {payoffQ.error && <EmptyState title="Couldn't load the payoff plan" hint={payoffQ.error} />}
            {!payoffQ.loading && payoffQ.data && (
              <>
                {payoffQ.data.missing_balance.length > 0 && (
                  <p className="carry-note carry-note-warn">
                    Marked as debt but missing a balance: {payoffQ.data.missing_balance.join(', ')}.
                    Edit the item and enter the balance off the latest statement to include it.
                  </p>
                )}
                {!payoffQ.data.plan || payoffQ.data.debts.length === 0 ? (
                  <EmptyState
                    title="No debts to calculate yet"
                    hint="Mark a carry item as Debt, then enter its balance, APR and monthly payment."
                  />
                ) : (
                  <>
                    <div className="carry-extra-row">
                      <label className="field">
                        <span className="field-label">Extra monthly payment ($)</span>
                        <input
                          className="input"
                          inputMode="decimal"
                          value={extra}
                          onChange={(e) => setExtra(e.target.value)}
                          placeholder="e.g. 100"
                        />
                      </label>
                    </div>
                    <div className="table-wrap">
                      <table className="carry-table">
                        <thead>
                          <tr>
                            <th>Debt</th>
                            <th className="num">Balance</th>
                            <th className="num">APR</th>
                            <th className="num">Monthly</th>
                            <th className="num">Min-only payoff</th>
                            <th className="num">With extra</th>
                          </tr>
                        </thead>
                        <tbody>
                          {payoffQ.data.debts.map((d) => (
                            <tr key={d.id}>
                              <td>{d.name}</td>
                              <td className="num tnum">{formatMoney(d.balance)}</td>
                              <td className="num tnum">{d.apr.toFixed(2)}%</td>
                              <td className="num tnum">{formatMoney(d.min_payment)}</td>
                              <td className="num tnum">
                                {payoffQ.data!.plan!.baseline.per_debt[d.id] != null
                                  ? `${payoffQ.data!.plan!.baseline.per_debt[d.id]} mo`
                                  : 'never'}
                              </td>
                              <td className="num tnum">
                                {payoffQ.data!.plan!.avalanche?.per_debt[d.id] != null
                                  ? `${payoffQ.data!.plan!.avalanche!.per_debt[d.id]} mo`
                                  : '—'}
                              </td>
                            </tr>
                          ))}
                          <tr className="carry-total-row">
                            <td>Debt-free by</td>
                            <td className="num tnum" colSpan={3} />
                            <td className="num tnum">
                              {payoffQ.data.plan.baseline.debt_free ?? 'never'} ·{' '}
                              {formatMoney(payoffQ.data.plan.baseline.total_interest)} interest
                            </td>
                            <td className="num tnum">
                              {payoffQ.data.plan.avalanche ? (
                                <>
                                  {payoffQ.data.plan.avalanche.debt_free ?? 'never'} ·{' '}
                                  {formatMoney(payoffQ.data.plan.avalanche.total_interest)} interest
                                  {payoffQ.data.plan.interest_saved != null &&
                                    payoffQ.data.plan.interest_saved > 0 && (
                                      <span className="carry-delta pos">
                                        {' '}
                                        (−{formatMoney(payoffQ.data.plan.interest_saved)})
                                      </span>
                                    )}
                                </>
                              ) : (
                                '—'
                              )}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <p className="carry-note">
                      Interest compounds monthly at each invoice APR. The extra payment targets the
                      highest-APR debt first (avalanche) and rolls freed minimums forward. Update
                      balances and APRs from each statement upload.
                    </p>
                  </>
                )}
              </>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
