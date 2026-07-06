import { useState } from 'react';
import { Trash2, Plus } from 'lucide-react';
import { fetchBudgets, fetchCategories, setBudget, deleteBudget } from '../services/api';
import { useAsync } from '../hooks/useAsync';
import type { Budget } from '../services/types';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Money, { formatMoney } from '../components/Money';
import ProgressBar from '../components/charts/ProgressBar';
import Spinner from '../components/Spinner';
import EmptyState from '../components/EmptyState';
import './Budgets.css';

function statusOf(b: Budget): 'ok' | 'warn' | 'over' {
  if (b.spent > b.limit_amount) return 'over';
  if (b.pct >= 80) return 'warn';
  return 'ok';
}

export default function Budgets() {
  const budgetsQ = useAsync<Budget[]>(fetchBudgets);
  const categoriesQ = useAsync<string[]>(fetchCategories);

  const [category, setCategory] = useState('');
  const [limit, setLimit] = useState('200');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');

  const categories = categoriesQ.data ?? [];
  const budgets = budgetsQ.data ?? [];

  async function save() {
    const cat = category.trim();
    const amt = parseFloat(limit);
    if (!cat || isNaN(amt) || amt <= 0) {
      setErr('Enter a category and a limit greater than 0.');
      return;
    }
    setSaving(true);
    setErr('');
    try {
      await setBudget(cat, amt);
      setCategory('');
      setLimit('200');
      budgetsQ.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Could not save budget.');
    } finally {
      setSaving(false);
    }
  }

  async function remove(cat: string) {
    await deleteBudget(cat);
    budgetsQ.reload();
  }

  return (
    <div className="stack">
      <PageHeader title="Budgets" subtitle="Set monthly limits and track spending against them" />

      <Card title="Set a budget">
        <div className="budget-form">
          <div className="field grow">
            <span className="field-label">Category</span>
            {categories.length > 0 ? (
              <select className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
                <option value="">Choose a category…</option>
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            ) : (
              <input
                className="input"
                placeholder="e.g. Food and Drink"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              />
            )}
          </div>
          <div className="field">
            <span className="field-label">Monthly limit ($)</span>
            <input
              className="input"
              type="number"
              min="1"
              step="25"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
            />
          </div>
          <button className="btn btn-primary budget-save" onClick={save} disabled={saving}>
            <Plus size={15} /> Save
          </button>
        </div>
        {err && <div className="section-error" style={{ marginTop: 10 }}>{err}</div>}
      </Card>

      {budgetsQ.loading ? (
        <Spinner center />
      ) : budgets.length === 0 ? (
        <Card>
          <EmptyState
            title="No budgets yet"
            hint="Set one above to start tracking a category against a monthly limit."
          />
        </Card>
      ) : (
        <div className="budget-list">
          {budgets.map((b) => {
            const status = statusOf(b);
            const over = status === 'over';
            return (
              <Card key={b.category}>
                <div className="budget-row">
                  <div className="budget-head">
                    <span className="budget-cat">{b.category}</span>
                    <span className="budget-amounts tnum">
                      {formatMoney(b.spent)} / {formatMoney(b.limit_amount)}
                    </span>
                  </div>
                  <ProgressBar pct={b.pct} status={status} />
                  <div className="budget-foot">
                    <span className={`budget-pct ${status}`}>{Math.round(b.pct)}% of budget</span>
                    <span className="budget-remaining">
                      {over ? (
                        <span className="over-text">
                          <Money value={Math.abs(b.remaining)} /> over
                        </span>
                      ) : (
                        <>
                          <Money value={b.remaining} /> left
                        </>
                      )}
                    </span>
                    <button
                      className="btn btn-sm budget-del"
                      onClick={() => remove(b.category)}
                      aria-label={`Delete ${b.category} budget`}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
