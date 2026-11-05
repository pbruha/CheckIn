import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { errorText } from '../lib/errors';
import { formatDateTime, statusLabel } from '../lib/format';
import type { MyAttendance } from '../lib/types';

export function StudentDashboard() {
  const [data, setData] = useState<MyAttendance | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<MyAttendance>('/me/attendance')
      .then(setData)
      .catch((err) => setError(errorText(err)));
  }, []);

  if (error) return <p className="error" role="alert">{error}</p>;
  if (!data) return <p className="muted">Načítání…</p>;

  const warning = data.remaining <= 1;
  return (
    <div className="stack-lg">
      <section className={`card ${warning ? 'card-warning' : ''}`}>
        <p>
          Absence: <strong>{data.absences}</strong> z {data.absence_limit} povolených
        </p>
        {data.remaining === 0 && data.absences > 0 && <p className="error">Dosáhl jste limitu absencí.</p>}
        {data.remaining === 1 && <p className="warning-text">Zbývá už jen 1 povolená absence.</p>}
        <div className="row wrap">
          <Link to="/student/checkin" className="button primary">Zapsat docházku</Link>
          <Link to="/student/excuses" className="button">Omluvenky</Link>
        </div>
      </section>

      <h2>Hodiny</h2>
      {data.items.length === 0 && <p className="muted">Zatím nejste zapsáni do žádné skupiny.</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Termín</th>
              <th>Skupina</th>
              <th>Stav</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((item) => (
              <tr key={item.session_id}>
                <td>{formatDateTime(item.starts_at)}</td>
                <td>{item.group_name}</td>
                <td>
                  {item.status === 'absent' && (
                    <Link to={`/student/excuses?session=${item.session_id}`} className="small">Omluvit → </Link>
                  )}
                  {item.status ? statusLabel(item.status) : item.session_status === 'ready' ? 'Naplánováno' : item.session_status === 'running' ? 'Probíhá' : 'Nezapsán'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
