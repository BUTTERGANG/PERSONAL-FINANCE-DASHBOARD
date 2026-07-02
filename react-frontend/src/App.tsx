import { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  ArrowLeftRight,
  Wallet,
  Link2,
  Target,
  RefreshCw,
  Repeat,
  Upload,
  Settings as SettingsIcon,
  Menu,
} from 'lucide-react';
import ThemeToggle from './components/ThemeToggle';
import { triggerSync } from './services/api';
import './App.css';

const navigation = [
  { to: '/overview', label: 'Overview', icon: LayoutDashboard },
  { to: '/transactions', label: 'Transactions', icon: ArrowLeftRight },
  { to: '/accounts', label: 'Accounts', icon: Wallet },
  { to: '/budgets', label: 'Budgets', icon: Target },
  { to: '/subscriptions', label: 'Subscriptions', icon: Repeat },
  { to: '/import', label: 'Import', icon: Upload },
  { to: '/link', label: 'Link account', icon: Link2 },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
];

const titles: Record<string, string> = Object.fromEntries(
  navigation.map((n) => [n.to, n.label]),
);

export default function App({ children }: { children?: React.ReactNode }) {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const pageTitle = titles[location.pathname] ?? 'Finance';

  async function handleSync() {
    setSyncing(true);
    try {
      await triggerSync();
      setToast('Sync started — balances update in the background.');
    } catch {
      setToast('Sync failed — is the backend running?');
    } finally {
      setSyncing(false);
      setTimeout(() => setToast(null), 4000);
    }
  }

  return (
    <div className="app">
      <aside className={`sidebar${mobileOpen ? ' open' : ''}`}>
        <div className="sidebar-header">
          <span className="logo">
            <Wallet size={20} />
          </span>
          <span className="logo-text">Finance</span>
        </div>
        <nav className="nav">
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              >
                <Icon size={18} className="nav-icon" />
                <span className="nav-label">{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </aside>

      {mobileOpen && <div className="sidebar-scrim" onClick={() => setMobileOpen(false)} />}

      <main className="main">
        <header className="header">
          <div className="header-left">
            <button
              className="btn btn-icon menu-btn"
              onClick={() => setMobileOpen((o) => !o)}
              aria-label="Toggle menu"
            >
              <Menu size={18} />
            </button>
            <h1 className="page-title">{pageTitle}</h1>
          </div>
          <div className="header-actions">
            <button className="btn" onClick={handleSync} disabled={syncing}>
              <RefreshCw size={16} className={syncing ? 'spin-icon' : ''} />
              <span className="sync-label">{syncing ? 'Syncing…' : 'Sync'}</span>
            </button>
            <ThemeToggle />
          </div>
        </header>
        <div className="content">
          {children}
          <Outlet />
        </div>
      </main>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
