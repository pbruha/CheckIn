import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth, isTeacher } from '../lib/auth';
import { ApiError } from '../lib/api';

export function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={from ?? (isTeacher(user.role) ? '/teacher' : '/student')} replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const signedIn = await login(email, password);
      navigate(from ?? (isTeacher(signedIn.role) ? '/teacher' : '/student'), { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Přihlášení se nezdařilo');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <h1>CheckIn</h1>
      <p className="muted">Docházka – Základy programátorské praxe</p>
      <form onSubmit={onSubmit} className="card stack">
        <label>
          E-mail
          <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Heslo
          <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" className="primary" disabled={busy}>
          {busy ? 'Přihlašuji…' : 'Přihlásit'}
        </button>
      </form>
    </div>
  );
}
