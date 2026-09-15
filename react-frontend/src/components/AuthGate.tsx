import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { Lock } from 'lucide-react';
import { fetchPinRequired, verifyPin } from '../services/api';
import { getPin, setPin, clearPin, onPinChange } from '../services/pin';
import Spinner from './Spinner';
import './AuthGate.css';

/**
 * Wraps the app. If the backend requires a PIN and none is stored (or a 401
 * cleared it), shows a lock screen. Otherwise renders children.
 */
export default function AuthGate({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<'checking' | 'locked' | 'open'>('checking');
  const [pin, setPinValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Initial check: does the backend want a PIN, and do we already have a valid one?
  useEffect(() => {
    let active = true;
    (async () => {
      const required = await fetchPinRequired();
      if (!active) return;
      if (!required) {
        setStatus('open');
        return;
      }
      // Gate is on. If we have a stored PIN, trust it — the first real API call
      // re-validates and a 401 will re-lock us via onPinChange below.
      setStatus(getPin() ? 'open' : 'locked');
    })();
    return () => {
      active = false;
    };
  }, []);

  // A 401 anywhere clears the stored PIN → re-lock.
  useEffect(() => {
    return onPinChange((p) => {
      if (p === null) {
        setStatus('locked');
        setError('Session expired — please re-enter your PIN.');
      }
    });
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!pin.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const ok = await verifyPin(pin);
      if (ok) {
        setPin(pin); // stores + notifies
        setPinValue('');
        setStatus('open');
      } else {
        // Clear first: clearPin() fires the onPinChange(null) listener, which
        // would otherwise overwrite this error with "Session expired". Set the
        // user-facing message AFTER so it wins.
        clearPin();
        setError('Incorrect PIN.');
      }
    } catch {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setSubmitting(false);
    }
  }

  if (status === 'checking') {
    return (
      <div className="gate-loading">
        <Spinner center />
      </div>
    );
  }

  if (status === 'locked') {
    return (
      <div className="gate">
        <form className="gate-card" onSubmit={handleSubmit}>
          <div className="gate-icon">
            <Lock size={22} />
          </div>
          <h1 className="gate-title">Dashboard locked</h1>
          <p className="gate-sub">Enter your PIN to continue.</p>
          <input
            className="input gate-input"
            type="password"
            inputMode="numeric"
            autoFocus
            autoComplete="current-password"
            placeholder="PIN"
            value={pin}
            onChange={(e) => setPinValue(e.target.value)}
            aria-label="Dashboard PIN"
          />
          {error && <div className="gate-error">{error}</div>}
          <button className="btn btn-primary gate-btn" type="submit" disabled={submitting}>
            {submitting ? 'Checking…' : 'Unlock'}
          </button>
        </form>
      </div>
    );
  }

  return <>{children}</>;
}
