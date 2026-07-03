import { useMemo, useRef, useState } from 'react';
import Papa from 'papaparse';
import { Upload, CheckCircle2, Plus, Save } from 'lucide-react';
import {
  fetchAccounts,
  createManualAccount,
  updateManualBalance,
  importTransactions,
} from '../services/api';
import { useAsync } from '../hooks/useAsync';
import type { Account, ImportTxnRow, ImportResult } from '../services/types';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Money from '../components/Money';
import Badge from '../components/Badge';
import Spinner from '../components/Spinner';
import EmptyState from '../components/EmptyState';
import './Import.css';

const MANUAL_TYPES = ['checking', 'savings', 'credit', 'investment', 'loan', 'asset', 'cash'];

type Tab = 'csv' | 'manual';

export default function Import() {
  const accountsQ = useAsync<Account[]>(fetchAccounts);
  const [tab, setTab] = useState<Tab>('csv');

  const reload = () => accountsQ.reload();

  return (
    <div className="stack">
      <PageHeader
        title="Import"
        subtitle="Track accounts and import bank-statement CSVs — no bank connection required."
      />

      <div className="tabs" role="tablist">
        <button
          role="tab"
          aria-selected={tab === 'csv'}
          className={`tab${tab === 'csv' ? ' active' : ''}`}
          onClick={() => setTab('csv')}
        >
          CSV transactions
        </button>
        <button
          role="tab"
          aria-selected={tab === 'manual'}
          className={`tab${tab === 'manual' ? ' active' : ''}`}
          onClick={() => setTab('manual')}
        >
          Manual accounts
        </button>
      </div>

      {accountsQ.loading ? (
        <Spinner center />
      ) : accountsQ.error ? (
        <div className="section-error">Couldn’t load accounts: {accountsQ.error}</div>
      ) : tab === 'csv' ? (
        <CsvImport accounts={accountsQ.data ?? []} />
      ) : (
        <ManualAccounts accounts={accountsQ.data ?? []} onChange={reload} />
      )}
    </div>
  );
}

// ── CSV import ────────────────────────────────────────────────────────────────

interface ParsedCsv {
  columns: string[];
  rows: Record<string, string>[];
}

function guessColumn(columns: string[], keywords: string[]): string {
  const hit = columns.find((c) => keywords.some((k) => c.toLowerCase().includes(k)));
  return hit ?? columns[0] ?? '';
}

function CsvImport({ accounts }: { accounts: Account[] }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? '');
  const [csv, setCsv] = useState<ParsedCsv | null>(null);
  const [fileName, setFileName] = useState('');
  const [parseError, setParseError] = useState('');

  const [dateCol, setDateCol] = useState('');
  const [amountCol, setAmountCol] = useState('');
  const [descCol, setDescCol] = useState('');
  const [catCol, setCatCol] = useState('(none)');
  const [flipSign, setFlipSign] = useState(true);

  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState('');
  const [skippedRows, setSkippedRows] = useState(0);

  function handleFile(file: File) {
    setParseError('');
    setResult(null);
    setImportError('');
    setFileName(file.name);
    Papa.parse<Record<string, string>>(file, {
      header: true,
      skipEmptyLines: true,
      complete: (out) => {
        const columns = (out.meta.fields ?? []).filter(Boolean);
        if (!columns.length || !out.data.length) {
          setCsv(null);
          setParseError('CSV has no rows or no header.');
          return;
        }
        setCsv({ columns, rows: out.data });
        setDateCol(guessColumn(columns, ['date', 'posted']));
        setAmountCol(guessColumn(columns, ['amount', 'amt', 'debit']));
        setDescCol(guessColumn(columns, ['desc', 'name', 'payee', 'memo']));
        setCatCol('(none)');
      },
      error: (err) => {
        setCsv(null);
        setParseError(`Could not parse CSV: ${err.message}`);
      },
    });
  }

  // Normalize dates to YYYY-MM-DD (the backend requires it strictly).
  function toIsoDate(raw: string): string | null {
    const s = (raw ?? '').trim();
    if (!s) return null;
    // Already ISO-ish
    const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
    // MM/DD/YYYY or M/D/YY
    const us = s.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$/);
    if (us) {
      let [, mo, da, yr] = us;
      if (yr.length === 2) yr = `20${yr}`;
      return `${yr}-${mo.padStart(2, '0')}-${da.padStart(2, '0')}`;
    }
    const d = new Date(s);
    if (!isNaN(d.getTime())) {
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
        d.getDate(),
      ).padStart(2, '0')}`;
    }
    return null;
  }

  const preview = useMemo(() => (csv ? csv.rows.slice(0, 5) : []), [csv]);

  const ready = csv && accountId && dateCol && amountCol && descCol;

  async function runImport() {
    if (!csv || !accountId) return;
    setImporting(true);
    setImportError('');
    setResult(null);

    const rows: ImportTxnRow[] = [];
    let skipped = 0;
    for (const r of csv.rows) {
      const date = toIsoDate(r[dateCol]);
      const rawAmt = (r[amountCol] ?? '').toString().replace(/[$,]/g, '').trim();
      const amt = parseFloat(rawAmt);
      const desc = (r[descCol] ?? '').toString().trim();
      if (!date || !desc || isNaN(amt)) {
        skipped++;
        continue;
      }
      const row: ImportTxnRow = { date, amount: flipSign ? -amt : amt, description: desc };
      if (catCol !== '(none)') {
        const cat = (r[catCol] ?? '').toString().trim();
        if (cat) row.category = cat;
      }
      rows.push(row);
    }
    setSkippedRows(skipped);

    if (!rows.length) {
      setImporting(false);
      setImportError('No valid rows found — check the column mapping and date format.');
      return;
    }

    try {
      const res = await importTransactions(accountId, rows);
      setResult(res);
    } catch (e) {
      setImportError(e instanceof Error ? e.message : 'Import failed.');
    } finally {
      setImporting(false);
    }
  }

  if (!accounts.length) {
    return (
      <Card>
        <EmptyState
          title="Create an account first"
          hint="Add a manual account (other tab) so imported transactions have somewhere to go."
        />
      </Card>
    );
  }

  return (
    <div className="stack">
      <Card title="1 · Destination account">
        <div className="field" style={{ maxWidth: 360 }}>
          <span className="field-label">Transactions will be added to</span>
          <select className="select" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.institution})
              </option>
            ))}
          </select>
        </div>
      </Card>

      <Card title="2 · Upload CSV">
        <div
          className="dropzone"
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files?.[0];
            if (f) handleFile(f);
          }}
        >
          <Upload size={22} strokeWidth={1.5} />
          <div className="dropzone-text">
            {fileName ? <strong>{fileName}</strong> : 'Click or drop a bank-statement CSV'}
          </div>
          <div className="dropzone-hint">Export a statement from your bank’s website as CSV.</div>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
            }}
          />
        </div>
        {parseError && <div className="section-error" style={{ marginTop: 12 }}>{parseError}</div>}
      </Card>

      {csv && (
        <>
          <Card title="3 · Map columns" action={<Badge variant="accent">{csv.rows.length} rows</Badge>}>
            <div className="map-grid">
              <ColSelect label="Date" cols={csv.columns} value={dateCol} onChange={setDateCol} />
              <ColSelect label="Amount" cols={csv.columns} value={amountCol} onChange={setAmountCol} />
              <ColSelect label="Description" cols={csv.columns} value={descCol} onChange={setDescCol} />
              <ColSelect
                label="Category (optional)"
                cols={['(none)', ...csv.columns]}
                value={catCol}
                onChange={setCatCol}
              />
            </div>
            <label className="flip-row">
              <input
                type="checkbox"
                checked={flipSign}
                onChange={(e) => setFlipSign(e.target.checked)}
              />
              <span>
                Flip amount signs
                <span className="flip-hint">
                  {' '}
                  — this app stores spending as positive. Most banks export spending as negative, so
                  leave this on.
                </span>
              </span>
            </label>

            <div className="preview-wrap">
              <table className="dtable preview">
                <thead>
                  <tr>
                    {csv.columns.map((c) => (
                      <th key={c} className={c === amountCol ? 'num' : ''}>
                        {c}
                        {c === dateCol && <Badge>date</Badge>}
                        {c === amountCol && <Badge variant="accent">amount</Badge>}
                        {c === descCol && <Badge>desc</Badge>}
                        {c === catCol && catCol !== '(none)' && <Badge>category</Badge>}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.map((r, i) => (
                    <tr key={i}>
                      {csv.columns.map((c) => (
                        <td key={c} className={c === amountCol ? 'num' : ''}>
                          {r[c]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="4 · Import">
            {result ? (
              <div className="import-result">
                <CheckCircle2 size={20} className="ok" />
                <div>
                  <strong>Imported {result.added} transactions</strong>
                  <div className="result-meta">
                    {result.skipped_duplicates > 0 && `${result.skipped_duplicates} duplicates skipped`}
                    {result.skipped_duplicates > 0 && skippedRows > 0 && ' · '}
                    {skippedRows > 0 && `${skippedRows} unparseable rows ignored`}
                    {result.skipped_duplicates === 0 && skippedRows === 0 && 'All rows imported cleanly.'}
                  </div>
                </div>
              </div>
            ) : (
              <>
                <button
                  className="btn btn-primary"
                  disabled={!ready || importing}
                  onClick={runImport}
                >
                  {importing ? <Spinner /> : <Upload size={15} />}
                  {importing ? 'Importing…' : `Import ${csv.rows.length} transactions`}
                </button>
                {importError && (
                  <div className="section-error" style={{ marginTop: 12 }}>{importError}</div>
                )}
              </>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

function ColSelect({
  label,
  cols,
  value,
  onChange,
}: {
  label: string;
  cols: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      <select className="select" value={value} onChange={(e) => onChange(e.target.value)}>
        {cols.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
    </div>
  );
}

// ── Manual accounts ───────────────────────────────────────────────────────────

function ManualAccounts({ accounts, onChange }: { accounts: Account[]; onChange: () => void }) {
  const manual = accounts.filter((a) => a.id.startsWith('manual-'));

  const [name, setName] = useState('');
  const [type, setType] = useState('checking');
  const [balance, setBalance] = useState('0');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  async function add() {
    if (!name.trim()) return;
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await createManualAccount(name.trim(), type, parseFloat(balance) || 0);
      setMsg(`Added ${name.trim()}`);
      setName('');
      setBalance('0');
      onChange();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Could not create account.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="stack">
      <Card title="Add a manual account">
        <p className="muted">
          For anything you track by hand: 401k, car value, mortgage, cash. Debts (credit/loan)
          subtract from net worth.
        </p>
        <div className="manual-add">
          <div className="field grow">
            <span className="field-label">Account name</span>
            <input
              className="input"
              placeholder="e.g. Fidelity 401k"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="field">
            <span className="field-label">Type</span>
            <select className="select" value={type} onChange={(e) => setType(e.target.value)}>
              {MANUAL_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <span className="field-label">Balance ($)</span>
            <input
              className="input"
              type="number"
              step="100"
              value={balance}
              onChange={(e) => setBalance(e.target.value)}
            />
          </div>
          <button className="btn btn-primary add-btn" disabled={saving || !name.trim()} onClick={add}>
            <Plus size={15} /> Add
          </button>
        </div>
        {msg && <div className="ok-msg">{msg}</div>}
        {err && <div className="section-error" style={{ marginTop: 10 }}>{err}</div>}
      </Card>

      <Card title="Update balances" action={<span className="muted-count">{manual.length}</span>}>
        {manual.length === 0 ? (
          <EmptyState title="No manual accounts yet" hint="Add one above to track it in net worth." />
        ) : (
          <div className="balance-list">
            {manual.map((a) => (
              <ManualBalanceRow key={a.id} account={a} onSaved={onChange} />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function ManualBalanceRow({ account, onSaved }: { account: Account; onSaved: () => void }) {
  const [value, setValue] = useState(String(account.balance));
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function save() {
    setSaving(true);
    setSaved(false);
    try {
      await updateManualBalance(account.id, parseFloat(value) || 0);
      setSaved(true);
      onSaved();
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="balance-row">
      <div>
        <div className="account-name">{account.name}</div>
        <div className="account-meta">{account.account_type}</div>
      </div>
      <div className="balance-edit">
        <Money value={account.balance} />
        <input
          className="input balance-input"
          type="number"
          step="100"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <button className="btn btn-sm" disabled={saving} onClick={save}>
          {saved ? <CheckCircle2 size={14} className="ok" /> : <Save size={14} />}
          {saved ? 'Saved' : 'Update'}
        </button>
      </div>
    </div>
  );
}
