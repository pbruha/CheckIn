import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { isTeacher, useAuth } from '../lib/auth';

export function Layout({ title, children }: { title: string; children: ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">CheckIn</Link>
        <nav>
          {isTeacher(user?.role) ? <Link to="/teacher">Skupiny</Link> : <Link to="/student">Docházka</Link>}
          <button className="link" onClick={logout}>Odhlásit</button>
        </nav>
      </header>
      <main className="container">
        <h1>{title}</h1>
        {children}
      </main>
    </div>
  );
}
