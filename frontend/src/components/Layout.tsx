/**
 * Main Layout Component
 * 
 * Provides the app shell with navigation and content area.
 */

import { Outlet, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import ThemeToggle from './ThemeToggle';
import './Layout.css';

function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const isActive = (path: string) => {
    return location.pathname === path ? 'active' : '';
  };

  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="sidebar-header">
          <h1>AI Finance</h1>
          <p className="user-email">{user?.email}</p>
        </div>

        <ul className="nav-menu">
          <li>
            <Link to="/dashboard" className={isActive('/dashboard')}>
              📊 Dashboard
            </Link>
          </li>
          <li>
            <Link to="/transactions" className={isActive('/transactions')}>
              💳 Transactions
            </Link>
          </li>
          <li>
            <Link to="/budgets" className={isActive('/budgets')}>
              💰 Budgets
            </Link>
          </li>
          <li>
            <Link to="/goals" className={isActive('/goals')}>
              🎯 Goals
            </Link>
          </li>
          <li>
            <Link to="/reports" className={isActive('/reports')}>
              📈 Reports
            </Link>
          </li>
        </ul>

        <div className="sidebar-footer">
          <ThemeToggle />
          <button onClick={handleLogout} className="logout-btn">
            🚪 Logout
          </button>
        </div>
      </nav>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}

export default Layout;
