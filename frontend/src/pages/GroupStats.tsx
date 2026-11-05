import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, downloadCsv } from '../lib/api';
import { errorText } from '../lib/errors';
import { formatDateTime } from '../lib/format';
import type { GroupStats as Stats } from '../lib/types';

export function GroupStats() {
  const { id } = useParams();
  const groupId = Number(id);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Stats>(`/groups/${groupId}/stats`)
      .then(setStats)
      .catch((err) => setError(errorText(err)));
  }, [groupId]);

  if (error) return <p className="error" role="alert">{error}</p>;
  if (!stats) return <p className="muted">Načítání…</p>;

  return (
    <div className="stack-lg">
      <div className="row between wrap">
        <p className="muted">Uzavřených hodin: {stats.closed_sessions} · limit absencí: {stats.absence_limit}</p>
        <button onClick={() => downloadCsv(`/groups/${groupId}/export.csv`, `docházka-${groupId}.csv`).catch((err) => setError(errorText(err)))}>
          Export CSV
        </button>
      </div>

      <h2>Studenti</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Student</th>
              <th>Přítomen</th>
              <th>Pozdě</th>
              <th>Omluven</th>
              <th>Nepřítomen</th>
              <th>Účast</th>
            </tr>
          </thead>
          <tbody>
            {stats.students.map((s) => (
              <tr key={s.user_id} className={s.over_limit ? 'row-warning' : undefined}>
                <td>
                  {s.name || s.email}
                  {s.over_limit && <span className="badge badge-warning">Nad limit absencí</span>}
                </td>
                <td>{s.present}</td>
                <td>{s.late}</td>
                <td>{s.excused}</td>
                <td>{s.absent}</td>
                <td>{s.attendance_rate === null ? '—' : `${Math.round(s.attendance_rate * 100)} %`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Hodiny</h2>
      {stats.sessions.length === 0 && <p className="muted">Zatím žádná uzavřená hodina.</p>}
      <ul className="list">
        {stats.sessions.map((s) => (
          <li key={s.session_id} className="row between">
            <span>{formatDateTime(s.starts_at)}</span>
            <span>{s.present} / {s.enrolled}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
