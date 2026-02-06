/**
 * Settings Page
 *
 * Comprehensive settings for profile, security, preferences, and data management.
 */

import { useState, useEffect } from 'react';
import {
  User,
  Lock,
  Palette,
  Bell,
  Download,
  Trash2,
  Shield,
  Save,
  Check,
  AlertTriangle,
  Moon,
  Sun,
  Monitor,
  LogOut,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { usePreferences } from '../contexts/PreferencesContext';
import { settingsApi } from '../api/settings';
import './SettingsPage.css';

type SettingsSection = 'profile' | 'security' | 'appearance' | 'notifications' | 'data' | 'account';

function SettingsPage() {
  const { user, updateUser, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const { preferences, updatePreference, formatDate } = usePreferences();
  
  const [activeSection, setActiveSection] = useState<SettingsSection>('profile');
  
  // Profile state
  const [firstName, setFirstName] = useState(user?.first_name || '');
  const [lastName, setLastName] = useState(user?.last_name || '');
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMessage, setProfileMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  
  // Password state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  
  // Data management state
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Update form when user changes
  useEffect(() => {
    if (user) {
      setFirstName(user.first_name || '');
      setLastName(user.last_name || '');
    }
  }, [user]);

  // Handle profile update
  const handleProfileUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileSaving(true);
    setProfileMessage(null);

    try {
      const updatedUser = await settingsApi.updateProfile({
        first_name: firstName || undefined,
        last_name: lastName || undefined,
      });
      
      if (updateUser) {
        updateUser(updatedUser);
      }
      
      setProfileMessage({ type: 'success', text: 'Profile updated successfully!' });
    } catch (err: any) {
      setProfileMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to update profile',
      });
    } finally {
      setProfileSaving(false);
    }
  };

  // Handle password change
  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordMessage(null);

    // Validate passwords
    if (newPassword !== confirmPassword) {
      setPasswordMessage({ type: 'error', text: 'New passwords do not match' });
      return;
    }

    if (newPassword.length < 12) {
      setPasswordMessage({ type: 'error', text: 'Password must be at least 12 characters' });
      return;
    }

    if (!/[a-z]/.test(newPassword)) {
      setPasswordMessage({ type: 'error', text: 'Password must contain a lowercase letter' });
      return;
    }

    if (!/[A-Z]/.test(newPassword)) {
      setPasswordMessage({ type: 'error', text: 'Password must contain an uppercase letter' });
      return;
    }

    if (!/\d/.test(newPassword)) {
      setPasswordMessage({ type: 'error', text: 'Password must contain a number' });
      return;
    }

    if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>/?~`]/.test(newPassword)) {
      setPasswordMessage({ type: 'error', text: 'Password must contain a special character' });
      return;
    }

    setPasswordSaving(true);

    try {
      await settingsApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });

      setPasswordMessage({ type: 'success', text: 'Password changed successfully!' });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setPasswordMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to change password',
      });
    } finally {
      setPasswordSaving(false);
    }
  };

  // Handle preference changes
  const handlePreferenceChange = (key: string, value: any) => {
    updatePreference(key as any, value);
    
    // If theme preference, also update the theme context
    if (key === 'theme') {
      setTheme(value);
    }
  };

  // Handle data export
  const handleExport = async () => {
    if (!user) return;
    
    setExporting(true);
    try {
      const blob = await settingsApi.exportData(user.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ai-finance-transactions-${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
      alert('Failed to export data. Please try again.');
    } finally {
      setExporting(false);
    }
  };

  // Handle delete all transactions
  const handleDeleteAllTransactions = async () => {
    if (!user || deleteConfirmText !== 'DELETE') return;
    
    setDeleting(true);
    try {
      await settingsApi.deleteAllTransactions(user.id);
      setShowDeleteConfirm(false);
      setDeleteConfirmText('');
      alert('All transactions have been deleted.');
    } catch (err) {
      console.error('Delete failed:', err);
      alert('Failed to delete transactions. Please try again.');
    } finally {
      setDeleting(false);
    }
  };

  const sections = [
    { id: 'profile' as const, label: 'Profile', icon: User },
    { id: 'security' as const, label: 'Security', icon: Shield },
    { id: 'appearance' as const, label: 'Appearance', icon: Palette },
    { id: 'notifications' as const, label: 'Notifications', icon: Bell },
    { id: 'data' as const, label: 'Data', icon: Download },
    { id: 'account' as const, label: 'Account', icon: LogOut },
  ];

  return (
    <div className="settings-page">
      <h1>Settings</h1>
      <p className="subtitle">Manage your account and preferences</p>

      <div className="settings-layout">
        <nav className="settings-nav">
          {sections.map((section) => (
            <button
              key={section.id}
              className={`settings-nav-item ${activeSection === section.id ? 'active' : ''}`}
              onClick={() => setActiveSection(section.id)}
            >
              <section.icon size={18} strokeWidth={1.5} />
              <span>{section.label}</span>
            </button>
          ))}
        </nav>

        <div className="settings-content">
          {/* Profile Section */}
          {activeSection === 'profile' && (
            <section className="settings-section">
              <h2><User size={20} strokeWidth={1.5} /> Profile Information</h2>
              <p className="section-description">Update your personal information</p>

              <form onSubmit={handleProfileUpdate} className="settings-form">
                {profileMessage && (
                  <div className={`message ${profileMessage.type}`}>
                    {profileMessage.type === 'success' ? <Check size={16} /> : <AlertTriangle size={16} />}
                    {profileMessage.text}
                  </div>
                )}

                <div className="form-group">
                  <label htmlFor="email">Email</label>
                  <input
                    id="email"
                    type="email"
                    value={user?.email || ''}
                    disabled
                    className="disabled"
                  />
                  <small>Email cannot be changed</small>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="firstName">First Name</label>
                    <input
                      id="firstName"
                      type="text"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      placeholder="John"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="lastName">Last Name</label>
                    <input
                      id="lastName"
                      type="text"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      placeholder="Doe"
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label>Member Since</label>
                  <p className="static-value">{user?.created_at ? formatDate(user.created_at) : 'N/A'}</p>
                </div>

                <button type="submit" className="btn-primary" disabled={profileSaving}>
                  <Save size={16} />
                  {profileSaving ? 'Saving...' : 'Save Changes'}
                </button>
              </form>
            </section>
          )}

          {/* Security Section */}
          {activeSection === 'security' && (
            <section className="settings-section">
              <h2><Lock size={20} strokeWidth={1.5} /> Security</h2>
              <p className="section-description">Manage your password and security settings</p>

              <form onSubmit={handlePasswordChange} className="settings-form">
                <h3>Change Password</h3>

                {passwordMessage && (
                  <div className={`message ${passwordMessage.type}`}>
                    {passwordMessage.type === 'success' ? <Check size={16} /> : <AlertTriangle size={16} />}
                    {passwordMessage.text}
                  </div>
                )}

                <div className="form-group">
                  <label htmlFor="currentPassword">Current Password</label>
                  <input
                    id="currentPassword"
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="newPassword">New Password</label>
                  <input
                    id="newPassword"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    autoComplete="new-password"
                    minLength={12}
                  />
                  <small>Min 12 characters with uppercase, lowercase, number, and special character</small>
                </div>

                <div className="form-group">
                  <label htmlFor="confirmPassword">Confirm New Password</label>
                  <input
                    id="confirmPassword"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    autoComplete="new-password"
                  />
                </div>

                <button type="submit" className="btn-primary" disabled={passwordSaving}>
                  <Lock size={16} />
                  {passwordSaving ? 'Changing...' : 'Change Password'}
                </button>
              </form>

              <div className="security-info">
                <h3>Security Tips</h3>
                <ul>
                  <li>Use a unique password that you don't use elsewhere</li>
                  <li>Enable two-factor authentication when available</li>
                  <li>Log out from devices you don't recognize</li>
                  <li>Review your account activity regularly</li>
                </ul>
              </div>
            </section>
          )}

          {/* Appearance Section */}
          {activeSection === 'appearance' && (
            <section className="settings-section">
              <h2><Palette size={20} strokeWidth={1.5} /> Appearance</h2>
              <p className="section-description">Customize how the app looks</p>

              <div className="settings-form">
                <div className="form-group">
                  <label>Theme</label>
                  <div className="theme-options">
                    <button
                      className={`theme-option ${theme === 'light' ? 'active' : ''}`}
                      onClick={() => handlePreferenceChange('theme', 'light')}
                    >
                      <Sun size={20} />
                      <span>Light</span>
                    </button>
                    <button
                      className={`theme-option ${theme === 'dark' ? 'active' : ''}`}
                      onClick={() => handlePreferenceChange('theme', 'dark')}
                    >
                      <Moon size={20} />
                      <span>Dark</span>
                    </button>
                    <button
                      className={`theme-option ${theme === 'system' ? 'active' : ''}`}
                      onClick={() => handlePreferenceChange('theme', 'system')}
                    >
                      <Monitor size={20} />
                      <span>System</span>
                    </button>
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="currency">Currency</label>
                  <select
                    id="currency"
                    value={preferences.currency}
                    onChange={(e) => handlePreferenceChange('currency', e.target.value)}
                  >
                    <option value="USD">USD ($)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="GBP">GBP (£)</option>
                    <option value="JPY">JPY (¥)</option>
                    <option value="INR">INR (₹)</option>
                    <option value="CAD">CAD (C$)</option>
                    <option value="AUD">AUD (A$)</option>
                    <option value="CHF">CHF (CHF)</option>
                    <option value="CNY">CNY (¥)</option>
                    <option value="KRW">KRW (₩)</option>
                    <option value="BRL">BRL (R$)</option>
                    <option value="MXN">MXN (MX$)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="dateFormat">Date Format</label>
                  <select
                    id="dateFormat"
                    value={preferences.dateFormat}
                    onChange={(e) => handlePreferenceChange('dateFormat', e.target.value)}
                  >
                    <option value="MM/DD/YYYY">MM/DD/YYYY</option>
                    <option value="DD/MM/YYYY">DD/MM/YYYY</option>
                    <option value="YYYY-MM-DD">YYYY-MM-DD</option>
                  </select>
                </div>
              </div>
            </section>
          )}

          {/* Notifications Section */}
          {activeSection === 'notifications' && (
            <section className="settings-section">
              <h2><Bell size={20} strokeWidth={1.5} /> Notifications</h2>
              <p className="section-description">Configure your notification preferences</p>

              <div className="settings-form">
                <div className="toggle-group">
                  <div className="toggle-item">
                    <div className="toggle-info">
                      <span className="toggle-label">Email Notifications</span>
                      <span className="toggle-description">Receive important updates via email</span>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={preferences.emailNotifications}
                        onChange={(e) => handlePreferenceChange('emailNotifications', e.target.checked)}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>

                  <div className="toggle-item">
                    <div className="toggle-info">
                      <span className="toggle-label">Budget Alerts</span>
                      <span className="toggle-description">Get notified when approaching budget limits</span>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={preferences.budgetAlerts}
                        onChange={(e) => handlePreferenceChange('budgetAlerts', e.target.checked)}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>

                  <div className="toggle-item">
                    <div className="toggle-info">
                      <span className="toggle-label">Weekly Reports</span>
                      <span className="toggle-description">Receive weekly spending summaries</span>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={preferences.weeklyReports}
                        onChange={(e) => handlePreferenceChange('weeklyReports', e.target.checked)}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* Data Section */}
          {activeSection === 'data' && (
            <section className="settings-section">
              <h2><Download size={20} strokeWidth={1.5} /> Data Management</h2>
              <p className="section-description">Export or delete your data</p>

              <div className="settings-form">
                <div className="data-card">
                  <div className="data-card-info">
                    <h3><Download size={18} /> Export Data</h3>
                    <p>Download all your financial data as a JSON file</p>
                  </div>
                  <button className="btn-secondary" onClick={handleExport} disabled={exporting}>
                    {exporting ? 'Exporting...' : 'Export'}
                  </button>
                </div>

                <div className="data-card danger">
                  <div className="data-card-info">
                    <h3><Trash2 size={18} /> Delete All Transactions</h3>
                    <p>Permanently delete all your transaction history. This cannot be undone.</p>
                  </div>
                  <button
                    className="btn-danger"
                    onClick={() => setShowDeleteConfirm(true)}
                  >
                    Delete All
                  </button>
                </div>

                {showDeleteConfirm && (
                  <div className="delete-confirm-modal">
                    <div className="delete-confirm-content">
                      <AlertTriangle size={48} className="warning-icon" />
                      <h3>Are you absolutely sure?</h3>
                      <p>
                        This action cannot be undone. This will permanently delete all your
                        transactions and associated data.
                      </p>
                      <p>Type <strong>DELETE</strong> to confirm:</p>
                      <input
                        type="text"
                        value={deleteConfirmText}
                        onChange={(e) => setDeleteConfirmText(e.target.value)}
                        placeholder="DELETE"
                      />
                      <div className="delete-confirm-actions">
                        <button
                          className="btn-secondary"
                          onClick={() => {
                            setShowDeleteConfirm(false);
                            setDeleteConfirmText('');
                          }}
                        >
                          Cancel
                        </button>
                        <button
                          className="btn-danger"
                          onClick={handleDeleteAllTransactions}
                          disabled={deleteConfirmText !== 'DELETE' || deleting}
                        >
                          {deleting ? 'Deleting...' : 'Delete All Transactions'}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* Account Section */}
          {activeSection === 'account' && (
            <section className="settings-section">
              <h2><LogOut size={20} strokeWidth={1.5} /> Account</h2>
              <p className="section-description">Sign out of your account</p>

              <div className="settings-form">
                <div className="data-card">
                  <div className="data-card-info">
                    <h3><LogOut size={18} /> Log Out</h3>
                    <p>Sign out of your account on this device</p>
                  </div>
                  <button
                    className="btn-danger"
                    onClick={async () => {
                      try {
                        await logout();
                      } catch (error) {
                        console.error('Logout failed:', error);
                      }
                    }}
                  >
                    Log Out
                  </button>
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

export default SettingsPage;
