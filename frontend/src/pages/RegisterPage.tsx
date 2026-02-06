/**
 * Register Page
 */

import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import ThemeToggle from '../components/ThemeToggle';
import './AuthPages.css';

function RegisterPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const passwordChecks = useMemo(() => ([
    { label: '12+ characters', met: password.length >= 12 },
    { label: 'Uppercase', met: /[A-Z]/.test(password) },
    { label: 'Lowercase', met: /[a-z]/.test(password) },
    { label: 'Number', met: /\d/.test(password) },
    { label: 'Special char', met: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>/?~`]/.test(password) },
  ]), [password]);

  const passwordStrength = useMemo(() => {
    const met = passwordChecks.filter(c => c.met).length;
    if (met === 0) return 0;
    return Math.round((met / passwordChecks.length) * 100);
  }, [passwordChecks]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    const failedCheck = passwordChecks.find(c => !c.met);
    if (failedCheck) {
      setError(`Password requirement not met: ${failedCheck.label}`);
      return;
    }

    setIsLoading(true);

    try {
      await register({
        email,
        password,
        first_name: firstName || undefined,
        last_name: lastName || undefined,
      });
      navigate('/dashboard');
    } catch (err: any) {
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        setError(typeof detail === 'string' ? detail : 'Registration failed. Please try again.');
      } else if (err.code === 'ERR_NETWORK' || err.message === 'Network Error') {
        setError('Cannot reach API. Check backend status, VITE_API_BASE_URL, and backend CORS ALLOWED_ORIGINS.');
      } else {
        setError('Registration failed. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-theme-toggle">
        <ThemeToggle />
      </div>
      <div className="auth-container">
        <div className="auth-header">
          <div className="auth-brand">
            <img src="/logo.svg" alt="Logo" className="auth-brand-logo" />
            <img src="/logo-text.svg" alt="Finheance" className="auth-brand-text" />
          </div>
          <p className="auth-subtitle">Create your account</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="error-message">{error}</div>}

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="firstName">First Name</label>
              <input
                id="firstName"
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="Jane"
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
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
              autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Min. 12 characters"
              autoComplete="new-password"
            />
            {password.length > 0 && (
              <div className="password-strength">
                <div className="strength-track">
                  <div
                    className="strength-fill"
                    style={{ width: `${passwordStrength}%` }}
                    data-strength={
                      passwordStrength <= 40 ? 'weak' :
                      passwordStrength <= 80 ? 'medium' : 'strong'
                    }
                  />
                </div>
                <div className="strength-checks">
                  {passwordChecks.map(c => (
                    <span key={c.label} className={`check-tag ${c.met ? 'met' : ''}`}>
                      {c.label}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              placeholder="Re-enter password"
              autoComplete="new-password"
            />
            {confirmPassword.length > 0 && password !== confirmPassword && (
              <small className="mismatch-hint">Passwords don't match</small>
            )}
          </div>

          <button type="submit" className="submit-btn" disabled={isLoading}>
            {isLoading ? (
              <span className="btn-loading">
                <span className="spinner" />
                Creating account
              </span>
            ) : (
              'Create Account'
            )}
          </button>
        </form>

        <div className="auth-footer">
          <p>
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default RegisterPage;
