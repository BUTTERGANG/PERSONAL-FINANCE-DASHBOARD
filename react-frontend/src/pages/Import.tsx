import { useMemo, useRef, useState } from 'react';
import Papa from 'papaparse';
import { Upload, CheckCircle2, Plus, Save, FileText, SkipForward } from 'lucide-react';
import {
  fetchAccounts,
  createManualAccount,
  updateManualBalance,
  importTransactions,
  previewPdfImport,
  confirmPdfImport,
} from '../services/api';
import { useAsync } from '../hooks/useAsync';
import type { Account, ImportTxnRow, ImportResult, ParsedTransaction } from '../services/types';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Money from '../components/Money';
import Badge from '../components/Badge';
import Spinner from '../components/Spinner';
import EmptyState from '../components/EmptyState';
import './Import.css';

const MANUAL_TYPES = ['checking', 'savings', 'credit', 'investment', 'loan', 'asset', 'cash'];

type Tab = 'csv' | 'pdf' | 'manual';

export default function Import() {
  const accountsQ = useAsync<Account[]>(fetchAccounts);
  const [tab, setTab] = useState<Tab>('csv');

  const reload = () => accountsQ.reload();

  return (
    <div className="stack">
      <PageHeader
        title="Import"
        subtitle="Track accounts and import bank statements — CSV or PDF, no bank connection required."
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
          aria-selected={tab === 'pdf'}
          className={`tab${tab === 'pdf' ? ' active' : ''}`}
          onClick={() => setTab('pdf')}
        >
          <FileText size={14} /> PDF statements
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
        <div className="section-error">Couldn't load accounts: {accountsQ.error}</div>
      ) : tab === 'csv' ? (
        <CsvImport accounts={accountsQ.data ?? []} />
      ) : tab === 'pdf' ? (
        <PdfImport accounts={accountsQ.data ?? []} />
      ) : (
        <ManualAccounts accounts={accountsQ.data ?? []} onChange={reload} />
      )}
    </div>
  );
}

// ── Shared helpers ─────────────────────────────────────────────────────────────

interface ParsedCsv {
  columns: string[];
  rows: Record<string, string>[];
}

function guessColumn(columns: string[], keywords: string[]): string {
  const hit = columns.find((c) => keywords.some((k) => c.toLowerCase().includes(k)));
  return hit ?? columns[0] ?? '';
}

// Normalize dates to YYYY-MM-DD (the backend requires it strictly).
function toIsoDate(raw: string): string | null {
  const s = (raw ?? '').trim();
  if (!s) return null;
  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
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

// ── CSV import (sequential multi-file wizard) ──────────────────────────────────

interface FileOutcome {
  name: string;
  status: 'imported' | 'skipped' | 'error';
  added?: number;
  skipped_duplicates?: number;
  unparseable?: number;
  error?: string;
}

function CsvImport({ accounts }: { accounts: Account[] }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? '');

  // The batch queue. `idx` points at the file currently being mapped/imported.
  // idx === -1 means no active file (either nothing queued, or batch finished).
  const [queue, setQueue] = useState<File[]>([]);
  const [idx, setIdx] = useState(-1);
  const [outcomes, setOutcomes] = useState<FileOutcome[]>([]);

  // Parse state for the *current* file only — reset each time we advance.
  const [csv, setCsv] = useState<ParsedCsv | null>(null);
  const [parseError, setParseError] = useState('');
  const [dateCol, setDateCol] = useState('');
  const [amountCol, setAmountCol] = useState('');
  const [descCol, setDescCol] = useState('');
  const [catCol, setCatCol] = useState('(none)');
  const [flipSign, setFlipSign] = useState(true);

  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState('');

  const current = idx >= 0 ? queue[idx] : null;
  const preview = useMemo(() => (csv ? csv.rows.slice(0, 5) : []), [csv]);
  const ready = !!(csv && accountId && dateCol && amountCol && descCol);

  // Parse a File into the current-file state and auto-guess column mappings.
  function parseFile(file: File) {
    setCsv(null);
    setParseError('');
    setImportError('');
    setDateCol('');
    setAmountCol('');
    setDescCol('');
    setCatCol('(none)');
    Papa.parse<Record<string, string>>(file, {
      header: true,
      skipEmptyLines: true,
      complete: (out) => {
        const columns = (out.meta.fields ?? []).filter(Boolean);
        if (!columns.length || !out.data.length) {
          setCsv(null);
          setParseError('This file has no rows or no header row.');
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
        setParseError(`Could not parse this file: ${err.message}`);
      },
    });
  }

  // User picked one or more files: start a fresh batch at file 0.
  function startBatch(files: FileList | null) {
    if (!files || files.length === 0) return;
    // De-dupe by name, keep only CSV-ish files.
    const seen = new Set<string>();
    const list = Array.from(files).filter((f) => {
      if (seen.has(f.name)) return false;
      seen.add(f.name);
      return /\.csv$/i.test(f.name) || f.type === 'text/csv' || f.type === '';
    });
    if (!list.length) {
      setParseError('No CSV files selected. (Use the PDF tab for PDF statements.)');
      return;
    }
    setQueue(list);
    setOutcomes([]);
    setIdx(0);
    parseFile(list[0]);
  }

  // Move to the next file, or finish the batch.
  function advance(record: FileOutcome) {
    setOutcomes((prev) => [...prev, record]);
    const next = idx + 1;
    if (next < queue.length) {
      setIdx(next);
      parseFile(queue[next]);
    } else {
      setIdx(-1); // batch complete
      setCsv(null);
    }
  }

  function skipCurrent() {
    if (!current) return;
    advance({ name: current.name, status: 'skipped' });
  }

  async function importCurrent() {
    if (!csv || !accountId || !current) return;
    setImporting(true);
    setImportError('');

    const rows: ImportTxnRow[] = [];
    let unparseable = 0;
    for (const r of csv.rows) {
      const date = toIsoDate(r[dateCol]);
      const rawAmt = (r[amountCol] ?? '').toString().replace(/[$,]/g, '').trim();
      const amt = parseFloat(rawAmt);
      const desc = (r[descCol] ?? '').toString().trim();
      if (!date || !desc || isNaN(amt)) {
        unparseable++;
        continue;
      }
      const row: ImportTxnRow = { date, amount: flipSign ? -amt : amt, description: desc };
      if (catCol !== '(none)') {
        const cat = (r[catCol] ?? '').toString().trim();
        if (cat) row.category = cat;
      }
      rows.push(row);
    }

    if (!rows.length) {
      setImporting(false);
      setImportError('No valid rows in this file — check the column mapping and date format.');
      return;
    }

    try {
      const res = await importTransactions(accountId, rows);
      advance({
        name: current.name,
        status: 'imported',
        added: res.added,
        skipped_duplicates: res.skipped_duplicates,
        unparseable,
      });
    } catch (e) {
      setImportError(e instanceof Error ? e.message : 'Import failed.');
    } finally {
      setImporting(false);
    }
  }

  function resetBatch() {
    setQueue([]);
    setIdx(-1);
    setOutcomes([]);
    setCsv(null);
    setParseError('');
    setImportError('');
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

  const batchDone = idx === -1 && outcomes.length > 0;
  const totalAdded = outcomes.reduce((s, o) => s + (o.added ?? 0), 0);
  const totalDupes = outcomes.reduce((s, o) => s + (o.skipped_duplicates ?? 0), 0);

  return (
    <div className="stack">
      <Card title="1 · Destination account">
        <div className="field" style={{ maxWidth: 360 }}>
          <span className="field-label">Transactions will be added to</span>
          <select
            className="select"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            disabled={idx >= 0}
          >
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.institution})
              </option>
            ))}
          </select>
          {idx >= 0 && (
            <span className="field-hint">Locked while a batch is in progress.</span>
          )}
        </div>
      </Card>

      {/* Upload — hidden once a batch is active so the wizard drives the flow. */}
      {idx < 0 && !batchDone && (
        <Card title="2 · Upload CSV files">
          <div
            className="dropzone"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              startBatch(e.dataTransfer.files);
            }}
          >
            <Upload size={22} strokeWidth={1.5} />
            <div className="dropzone-text">Click or drop bank-statement CSVs</div>
            <div className="dropzone-hint">
              Select multiple files to import them one after another — each gets its own column
              mapping.
            </div>
            <input
              ref={inputRef}
              type="file"
              accept=".csv,text/csv"
              multiple
              hidden
              onChange={(e) => {
                startBatch(e.target.files);
                e.target.value = ''; // allow re-selecting the same files
              }}
            />
          </div>
          {parseError && (
            <div className="section-error" style={{ marginTop: 12 }}>
              {parseError}
            </div>
          )}
        </Card>
      )}

      {/* Wizard progress */}
      {idx >= 0 && current && (
        <>
          <div className="wizard-progress">
            <span className="wizard-step">
              File {idx + 1} of {queue.length}
            </span>
            <strong className="wizard-file">{current.name}</strong>
            <Badge variant="accent">{(current.size / 1024).toFixed(1)} KB</Badge>
          </div>

          {parseError ? (
            <Card title="Couldn't read this file">
              <div className="section-error">{parseError}</div>
              <div className="wizard-actions" style={{ marginTop: 12 }}>
                <button className="btn" onClick={skipCurrent}>
                  <SkipForward size={14} /> Skip this file
                </button>
              </div>
            </Card>
          ) : csv ? (
            <>
              <Card
                title="Map columns"
                action={<Badge variant="accent">{csv.rows.length} rows</Badge>}
              >
                <div className="map-grid">
                  <ColSelect label="Date" cols={csv.columns} value={dateCol} onChange={setDateCol} />
                  <ColSelect
                    label="Amount"
                    cols={csv.columns}
                    value={amountCol}
                    onChange={setAmountCol}
                  />
                  <ColSelect
                    label="Description"
                    cols={csv.columns}
                    value={descCol}
                    onChange={setDescCol}
                  />
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
                      — this app stores spending as positive. Most banks export spending as
                      negative, so leave this on.
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

              <Card title="Import this file">
                <div className="wizard-actions">
                  <button
                    className="btn btn-primary"
                    disabled={!ready || importing}
                    onClick={importCurrent}
                  >
                    {importing ? <Spinner /> : <Upload size={15} />}
                    {importing
                      ? 'Importing…'
                      : idx + 1 < queue.length
                        ? `Import & next (${csv.rows.length} rows)`
                        : `Import ${csv.rows.length} rows`}
                  </button>
                  <button className="btn" disabled={importing} onClick={skipCurrent}>
                    <SkipForward size={14} /> Skip
                  </button>
                  <button className="btn btn-ghost" disabled={importing} onClick={resetBatch}>
                    Cancel batch
                  </button>
                </div>
                {importError && (
                  <div className="section-error" style={{ marginTop: 12 }}>
                    {importError}
                  </div>
                )}
              </Card>
            </>
          ) : (
            <Card>
              <Spinner center />
            </Card>
          )}
        </>
      )}

      {/* Batch summary */}
      {batchDone && (
        <Card
          title="Import complete"
          action={<Badge variant="accent">{outcomes.length} files</Badge>}
        >
          <div className="import-result">
            <CheckCircle2 size={20} className="ok" />
            <div>
              <strong>
                Imported {totalAdded} transactions across{' '}
                {outcomes.filter((o) => o.status === 'imported').length} file
                {outcomes.filter((o) => o.status === 'imported').length === 1 ? '' : 's'}
              </strong>
              {totalDupes > 0 && (
                <div className="result-meta">{totalDupes} duplicates skipped</div>
              )}
            </div>
          </div>

          <div className="outcome-list">
            {outcomes.map((o, i) => (
              <div key={i} className="outcome-row">
                <span className="outcome-name">{o.name}</span>
                {o.status === 'imported' ? (
                  <span className="outcome-detail">
                    +{o.added} added
                    {o.skipped_duplicates ? ` · ${o.skipped_duplicates} dupes` : ''}
                    {o.unparseable ? ` · ${o.unparseable} skipped` : ''}
                  </span>
                ) : o.status === 'skipped' ? (
                  <Badge variant="warn">skipped</Badge>
                ) : (
                  <span className="outcome-detail err">{o.error ?? 'error'}</span>
                )}
              </div>
            ))}
          </div>

          <div className="wizard-actions" style={{ marginTop: 16 }}>
            <button className="btn btn-primary" onClick={resetBatch}>
              Import more files
            </button>
          </div>
        </Card>
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

// ── PDF import ─────────────────────────────────────────────────────────────────

function PdfImport({ accounts }: { accounts: Account[] }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? '');
  const [fileName, setFileName] = useState('');

  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState('');
  const [bankDetected, setBankDetected] = useState('');
  const [txns, setTxns] = useState<ParsedTransaction[] | null>(null);

  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState('');
  const [result, setResult] = useState<ImportResult | null>(null);

  const preview = useMemo(() => (txns ? txns.slice(0, 8) : []), [txns]);

  async function handleFile(file: File) {
    if (!/\.pdf$/i.test(file.name)) {
      setParseError('Please select a PDF statement.');
      return;
    }
    setFileName(file.name);
    setParseError('');
    setImportError('');
    setResult(null);
    setTxns(null);
    setBankDetected('');
    setParsing(true);
    try {
      const res = await previewPdfImport(file);
      setBankDetected(res.bank_detected);
      setTxns(res.transactions);
      if (!res.transactions.length) {
        setParseError('No transactions found in this PDF. Try the CSV tab instead.');
      }
    } catch (e) {
      setParseError(e instanceof Error ? e.message : 'Could not parse the PDF.');
    } finally {
      setParsing(false);
    }
  }

  async function runImport() {
    if (!txns || !accountId || !txns.length) return;
    setImporting(true);
    setImportError('');
    try {
      const res = await confirmPdfImport(accountId, txns);
      setResult(res);
    } catch (e) {
      setImportError(e instanceof Error ? e.message : 'Import failed.');
    } finally {
      setImporting(false);
    }
  }

  function reset() {
    setFileName('');
    setTxns(null);
    setBankDetected('');
    setParseError('');
    setImportError('');
    setResult(null);
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

      <Card title="2 · Upload PDF statement">
        <div
          className="dropzone"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files?.[0];
            if (f) handleFile(f);
          }}
        >
          {parsing ? <Spinner /> : <FileText size={22} strokeWidth={1.5} />}
          <div className="dropzone-text">
            {fileName ? <strong>{fileName}</strong> : 'Click or drop a bank-statement PDF'}
          </div>
          <div className="dropzone-hint">
            The statement is parsed on the server; nothing is saved until you confirm.
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,application/pdf"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
              e.target.value = '';
            }}
          />
        </div>
        {parseError && (
          <div className="section-error" style={{ marginTop: 12 }}>
            {parseError}
          </div>
        )}
      </Card>

      {txns && txns.length > 0 && (
        <>
          <Card
            title="3 · Review parsed transactions"
            action={
              <div className="pdf-review-meta">
                {bankDetected && <Badge>{bankDetected}</Badge>}
                <Badge variant="accent">{txns.length} transactions</Badge>
              </div>
            }
          >
            <div className="preview-wrap">
              <table className="dtable preview">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Description</th>
                    <th className="num">Amount</th>
                    <th>Category</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.map((t, i) => (
                    <tr key={i}>
                      <td>{t.date}</td>
                      <td>{t.description}</td>
                      <td className="num">
                        <Money value={t.amount} />
                      </td>
                      <td>{t.category ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {txns.length > preview.length && (
              <div className="dropzone-hint" style={{ marginTop: 8 }}>
                Showing first {preview.length} of {txns.length}.
              </div>
            )}
          </Card>

          <Card title="4 · Confirm import">
            {result ? (
              <div className="import-result">
                <CheckCircle2 size={20} className="ok" />
                <div>
                  <strong>Imported {result.added} transactions</strong>
                  <div className="result-meta">
                    {result.skipped_duplicates > 0
                      ? `${result.skipped_duplicates} duplicates skipped`
                      : 'All rows imported cleanly.'}
                  </div>
                  <div className="wizard-actions" style={{ marginTop: 12 }}>
                    <button className="btn btn-primary" onClick={reset}>
                      Import another PDF
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <>
                <button
                  className="btn btn-primary"
                  disabled={importing}
                  onClick={runImport}
                >
                  {importing ? <Spinner /> : <Upload size={15} />}
                  {importing ? 'Importing…' : `Import ${txns.length} transactions`}
                </button>
                {importError && (
                  <div className="section-error" style={{ marginTop: 12 }}>
                    {importError}
                  </div>
                )}
              </>
            )}
          </Card>
        </>
      )}
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
