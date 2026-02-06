/**
 * Main Layout Component
 *
 * Provides the app shell with collapsible sidebar navigation.
 */

import { useState } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  LayoutDashboard,
  ArrowLeftRight,
  Wallet,
  Target,
  BarChart3,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import OmniBar from './OmniBar';
import './Layout.css';

function Layout() {
  const { user } = useAuth();
  const location = useLocation();
  const [sidebarPinned, setSidebarPinned] = useState(false);
  const [sidebarHover, setSidebarHover] = useState(false);

  const isExpanded = sidebarPinned || sidebarHover;

  const displayName = user?.first_name && user?.last_name
    ? `${user.first_name} ${user.last_name}`
    : user?.email;

  const isActive = (path: string) => {
    return location.pathname === path ? 'active' : '';
  };

  const navItems = [
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/transactions', icon: ArrowLeftRight, label: 'Transactions' },
    { path: '/budgets', icon: Wallet, label: 'Budgets' },
    { path: '/goals', icon: Target, label: 'Goals' },
    { path: '/reports', icon: BarChart3, label: 'Reports' },
    { path: '/settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <div className="layout">
      <nav
        className={`sidebar ${isExpanded ? 'expanded' : 'collapsed'}`}
        onMouseEnter={() => setSidebarHover(true)}
        onMouseLeave={() => setSidebarHover(false)}
      >
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <img src="/logo.svg" alt="Logo" className="brand-logo" />
            <img src="/logo-text.svg" alt="Finheance" className="brand-text-img" />
          </div>
          <p className="user-email">{displayName}</p>
        </div>

        <ul className="nav-menu">
          {navItems.map((item) => (
            <li key={item.path}>
              <Link to={item.path} className={`nav-link ${isActive(item.path)}`}>
                <item.icon size={20} strokeWidth={1.5} />
                <span className="nav-label">{item.label}</span>
              </Link>
            </li>
          ))}
        </ul>

        <div className="sidebar-footer">
          <div className="footer-controls">
            <ThemeToggle />
            <button
              onClick={() => setSidebarPinned(!sidebarPinned)}
              className="sidebar-toggle"
              title={sidebarPinned ? 'Collapse sidebar' : 'Pin sidebar'}
            >
              {sidebarPinned ? (
                <PanelLeftClose size={18} strokeWidth={1.5} />
              ) : (
                <PanelLeftOpen size={18} strokeWidth={1.5} />
              )}
            </button>
          </div>
        </div>
      </nav>

      <main className="main-content">
        <div className="main-top-bar">
          <OmniBar />
        </div>
        <Outlet />
      </main>
    </div>
  );
}

export default Layout;
