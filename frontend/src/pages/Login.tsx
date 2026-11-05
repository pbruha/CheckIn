import { useEffect, useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth, isTeacher } from '../lib/auth';
import { api, ApiError, setToken } from '../lib/api';

type SsoConfig = { enabled: boolean; password_login: boolean };

/** Návrat z přihlášení školním účtem: token nebo chyba jsou v fragmentu adresy (neposílají se na server). */
function readSsoHash(): { token?: string; error?: string } {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  const token = params.get('token') ?? undefined;
  const error = params.get('sso_error') ?? undefined;
  if (token || error) window.history.replaceState(null, '', window.location.pathname);
  return { token, error: error ? decodeURIComponent(error) : undefined };
}

export function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sso, setSso] = useState<SsoConfig | null>(null);

  useEffect(() => {
    const { token, error: ssoError } = readSsoHash();
    if (token) {
      // Plné načtení, aby AuthProvider při startu načetl přihlášeného uživatele.
      setToken(token);
      window.location.replace('/');
      return;
    }
    if (ssoError) setError(ssoError);
    api<SsoConfig>('/auth/sso/config')
      .then(setSso)
      .catch(() => setSso({ enabled: false, password_login: true }));
  }, []);

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

  const showPasswordForm = !sso || !sso.enabled || sso.password_login;

  return (
    <div className="login">
      <h1>CheckIn</h1>
      <p className="muted">Docházka – Základy programátorské praxe</p>
      <div className="card stack">
        {sso?.enabled && (
          <a className="button primary" href="/api/auth/sso/login">Přihlásit školním účtem</a>
        )}
        {sso?.enabled && showPasswordForm && <p className="muted small center">nebo heslem</p>}
        {showPasswordForm && (
          <form onSubmit={onSubmit} className="stack">
            <label>
              E-mail
              <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label>
              Heslo
              <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            <button type="submit" className="primary" disabled={busy}>
              {busy ? 'Přihlašuji…' : 'Přihlásit'}
            </button>
          </form>
        )}
        {error && <p className="error" role="alert">{error}</p>}
      </div>
    </div>
  );
}
