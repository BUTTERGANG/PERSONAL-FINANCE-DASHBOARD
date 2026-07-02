import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import './theme/theme.css';
import './components/components.css';
import { applyStoredTheme } from './components/ThemeToggle';
import App from './App';
import Overview from './pages/Overview';
import Transactions from './pages/Transactions';
import Accounts from './pages/Accounts';
import LinkAccount from './pages/LinkAccount';
import Settings from './pages/Settings';
import Budgets from './pages/Budgets';
import Subscriptions from './pages/Subscriptions';
import Import from './pages/Import';

applyStoredTheme();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="/accounts" element={<Accounts />} />
          <Route path="/budgets" element={<Budgets />} />
          <Route path="/subscriptions" element={<Subscriptions />} />
          <Route path="/import" element={<Import />} />
          <Route path="/link" element={<LinkAccount />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
