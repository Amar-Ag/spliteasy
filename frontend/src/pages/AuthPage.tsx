import { useState, type FormEvent } from 'react';
import { errorMessage } from '../apiError';
import { useAuth } from '../auth/AuthContext';

type Mode = 'login' | 'register';

export function AuthPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<Mode>('login');
  const [identifier, setIdentifier] = useState('');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === 'login') await login({ identifier, password });
      else await register({ email, username, password });
      // On success the router redirects away from this page.
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  }

  function fillDemoAccount() {
    setError(null);
    setIdentifier('alice');
    setPassword('password123');
    setMode('login');
  }

  return (
    <div className="auth-shell">
      <div className="auth-intro">
        <h1 className="brand brand-large">
          Split<span>Easy</span>
        </h1>
        <p>Share costs with friends, roommates and travel buddies — and always know who owes whom.</p>
      </div>

      <form className="card auth-card" onSubmit={onSubmit}>
        <div className="segmented segmented-full" role="tablist">
          <button type="button" role="tab" aria-selected={mode === 'login'} className={mode === 'login' ? 'active' : ''} onClick={() => switchMode('login')}>
            Log in
          </button>
          <button type="button" role="tab" aria-selected={mode === 'register'} className={mode === 'register' ? 'active' : ''} onClick={() => switchMode('register')}>
            Create account
          </button>
        </div>

        {mode === 'login' ? (
          <label className="field">
            <span>Email or username</span>
            <input value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="username" required autoFocus />
          </label>
        ) : (
          <>
            <label className="field">
              <span>Email</span>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required autoFocus />
            </label>
            <label className="field">
              <span>Username</span>
              <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
              <small className="hint">Friends can add you to groups with this.</small>
            </label>
          </>
        )}

        <label className="field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            minLength={mode === 'register' ? 8 : undefined}
            required
          />
          {mode === 'register' && <small className="hint">At least 8 characters.</small>}
        </label>

        {error && <p className="error" role="alert">{error}</p>}

        <button className="btn btn-primary btn-block" disabled={submitting}>
          {submitting ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
        </button>

        <div className="demo-note">
          <strong>Demo accounts</strong> — <code>alice</code>, <code>bob</code>, <code>carol</code> or <code>dave</code> with
          password <code>password123</code>. Demo data resets when the backend restarts.{' '}
          <button type="button" className="btn-link" onClick={fillDemoAccount}>
            Use demo account
          </button>
        </div>
      </form>
    </div>
  );
}
