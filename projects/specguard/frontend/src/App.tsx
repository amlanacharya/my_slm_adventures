import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from './api';

export function App() {
  const location = useLocation();
  const settingsQuery = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.getSettings(),
    refetchInterval: 30_000,
  });

  const settings = settingsQuery.data;
  const providerLabel = settings
    ? `${settings.provider}${settings.model ? ` · ${settings.model}` : ''}`
    : '…';

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-logo">S</span>
          SpecGuard
        </div>
        <nav>
          <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : '')}>
            Generate
          </NavLink>
          <NavLink to="/history" className={({ isActive }) => (isActive ? 'active' : '')}>
            History
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => (isActive ? 'active' : '')}>
            Settings
          </NavLink>
        </nav>
        <div className="spacer" />
        <span className="chip" title="Active LLM provider">
          <span className="dot" />
          {providerLabel}
        </span>
      </header>
      <main className="route" key={location.pathname}>
        <Outlet />
      </main>
    </div>
  );
}
