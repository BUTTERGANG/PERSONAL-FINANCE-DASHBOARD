/**
 * Dashboard PIN handling (frontend side).
 *
 * The PIN is kept in sessionStorage — it survives page reloads within a tab but
 * clears when the tab closes, so a shared/kiosk browser doesn't leave the
 * dashboard unlocked. Every API call sends it in the `X-Dashboard-Pin` header
 * (see api.ts); the backend rejects /api/* without a valid PIN when one is set.
 */

const KEY = 'dashboard_pin';
const HEADER = 'X-Dashboard-Pin';

type Listener = (pin: string | null) => void;
const listeners = new Set<Listener>();

export function getPin(): string | null {
  return sessionStorage.getItem(KEY);
}

export function setPin(pin: string): void {
  sessionStorage.setItem(KEY, pin);
  listeners.forEach((l) => l(pin));
}

export function clearPin(): void {
  sessionStorage.removeItem(KEY);
  listeners.forEach((l) => l(null));
}

/** Subscribe to lock/unlock changes (e.g. a 401 clearing the PIN). Returns an unsubscribe fn. */
export function onPinChange(l: Listener): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

/** Header object to spread into fetch(); empty when no PIN is stored. */
export function pinHeader(): Record<string, string> {
  const pin = getPin();
  return pin ? { [HEADER]: pin } : {};
}
