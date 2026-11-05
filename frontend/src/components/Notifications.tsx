import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { api } from '../lib/api';
import type { Notification } from '../lib/types';

/** Upozornění v hlavičce stránky: limit absencí, rozhodnutí o omluvenkách, čekající omluvenky. */
export function Notifications() {
  const location = useLocation();
  const [items, setItems] = useState<Notification[]>([]);

  useEffect(() => {
    api<Notification[]>('/me/notifications')
      .then(setItems)
      .catch(() => setItems([]));
  }, [location.pathname]);

  if (items.length === 0) return null;
  return (
    <ul className="notifications" aria-label="Upozornění">
      {items.map((n, i) => (
        <li key={i} className={`notice notice-${n.level}`}>
          {n.group && <strong>{n.group}: </strong>}
          {n.text}
          {n.note && <span className="muted small"> – {n.note}</span>}
        </li>
      ))}
    </ul>
  );
}
