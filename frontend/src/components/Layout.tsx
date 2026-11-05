import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { isTeacher, useAuth } from '../lib/auth';
import { Notifications } from './Notifications';
import { PushToggle } from './PushToggle';

export function Layout({ title, children }: { title: string; children: ReactNode }) {
  const { user, logout } = useAuth();
  const teacher = isTeacher(user?.role);
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">CheckIn</Link>
        <nav>
          {teacher ? (
            <>
              <Link to="/teacher">Skupiny</Link>
              <Link to="/teacher/excuses">Omluvenky</Link>
            </>
          ) : (
            <>
              <Link to="/student">Docházka</Link>
              <Link to="/student/excuses">Omluvenky</Link>
            </>
          )}
          <button className="link" onClick={logout}>Odhlásit</button>
        </nav>
      </header>
      <main className="container">
        <Notifications />
        <h1>{title}</h1>
        <PushToggle />
        {children}
      </main>
    </div>
  );
}
