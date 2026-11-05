import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, downloadCsv } from '../lib/api';
import { errorText } from '../lib/errors';
import { getCurrentCoords } from '../lib/geo';
import { formatTime, formatDateTime, isSameLocalDay, statusLabel, toLocalInputValue } from '../lib/format';
import type { Lesson, MyGroup } from '../lib/types';

export function TeacherDashboard() {
  const [groups, setGroups] = useState<MyGroup[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<MyGroup[]>('/me/groups')
      .then((all) => setGroups(all.filter((g) => g.role === 'teacher')))
      .catch((err) => setError(errorText(err)));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!groups) return <p className="muted">Načítání…</p>;
  if (groups.length === 0) return <p className="muted">Zatím nemáte žádnou skupinu. Vytvořte ji přes API nebo CLI.</p>;
  return (
    <div className="stack-lg">
      {groups.map((g) => (
        <GroupCard key={g.id} group={g} />
      ))}
    </div>
  );
}

function GroupCard({ group }: { group: MyGroup }) {
  const navigate = useNavigate();
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [reload, setReload] = useState(0);
  const [starts, setStarts] = useState('');
  const [ends, setEnds] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Lesson[]>(`/groups/${group.id}/sessions`)
      .then(setLessons)
      .catch((err) => setError(errorText(err)));
  }, [group.id, reload]);

  async function createLesson(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api(`/groups/${group.id}/sessions`, {
        method: 'POST',
        json: { starts_at: new Date(starts).toISOString(), ends_at: new Date(ends).toISOString() },
      });
      setStarts('');
      setEnds('');
      setReload((r) => r + 1);
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function startLesson(lesson: Lesson) {
    setError(null);
    try {
      await api(`/sessions/${lesson.id}/start`, { method: 'POST' });
      navigate(`/teacher/sessions/${lesson.id}`);
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function importStudents(file: File) {
    setError(null);
    setMessage(null);
    try {
      const result = await api<{ created_users: number; enrolled: number; skipped_rows: number }>(
        `/groups/${group.id}/students/import`,
        { method: 'POST', body: await file.text(), headers: { 'Content-Type': 'text/csv' } },
      );
      setMessage(
        `Import: nových účtů ${result.created_users}, zapsáno ${result.enrolled}, přeskočeno řádků ${result.skipped_rows}.`,
      );
    } catch (err) {
      setError(errorText(err));
    }
  }

  const now = new Date();
  const today = lessons.filter((l) => isSameLocalDay(l.starts_at, now));
  const others = lessons.filter((l) => !isSameLocalDay(l.starts_at, now));

  return (
    <section className="card stack">
      <div className="row between wrap">
        <h2>{group.name}</h2>
        <div className="row wrap">
          <Link to={`/teacher/groups/${group.id}/stats`} className="button">Statistiky</Link>
          <button onClick={() => downloadCsv(`/groups/${group.id}/export.csv`, `docházka-${group.id}.csv`).catch((err) => setError(errorText(err)))}>
            Export CSV
          </button>
        </div>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {message && <p className="success">{message}</p>}

      <h3>Dnešní hodiny</h3>
      {today.length === 0 && <p className="muted">Dnes nejsou žádné hodiny.</p>}
      <LessonList lessons={today} onStart={startLesson} />

      <h3>Ostatní hodiny</h3>
      {others.length === 0 && <p className="muted">Žádné další hodiny.</p>}
      <LessonList lessons={others} onStart={startLesson} />

      <details>
        <summary>Přidat hodinu</summary>
        <form onSubmit={createLesson} className="stack">
          <label>
            Začátek
            <input type="datetime-local" required value={starts} onChange={(e) => setStarts(e.target.value)} />
          </label>
          <label>
            Konec
            <input type="datetime-local" required value={ends} onChange={(e) => setEnds(e.target.value)} />
          </label>
          <button type="button" className="link" onClick={() => {
            const start = new Date();
            start.setMinutes(0, 0, 0);
            setStarts(toLocalInputValue(start));
            setEnds(toLocalInputValue(new Date(start.getTime() + 60 * 60 * 1000)));
          }}>
            Vyplnit aktuální hodinu
          </button>
          <button type="submit" className="primary">Vytvořit hodinu</button>
        </form>
      </details>

      <RoomLocation groupId={group.id} />

      <details>
        <summary>Import studentů (CSV)</summary>
        <p className="muted small">Soubor s hlavičkou <code>email,name</code>. Účty bez hesla se vytvoří jako studentské.</p>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) importStudents(file);
            e.target.value = '';
          }}
        />
      </details>
    </section>
  );
}

function LessonList({ lessons, onStart }: { lessons: Lesson[]; onStart: (l: Lesson) => void }) {
  if (lessons.length === 0) return null;
  return (
    <ul className="list">
      {lessons.map((l) => (
        <li key={l.id} className="row between wrap">
          <span>
            {formatDateTime(l.starts_at)} – {formatTime(l.ends_at)}{' '}
            <span className={`badge badge-${l.status}`}>{statusLabel(l.status)}</span>
          </span>
          {l.status === 'ready' ? (
            <button className="primary" onClick={() => onStart(l)}>Spustit docházku</button>
          ) : (
            <Link to={`/teacher/sessions/${l.id}`} className="button">Otevřít</Link>
          )}
        </li>
      ))}
    </ul>
  );
}

type Location = { enabled: boolean; latitude: number | null; longitude: number | null; radius_m: number | null };

/** Geofence učebny: nastavení podle aktuální polohy vyučujícího, kterou má mít ve třídě. */
function RoomLocation({ groupId }: { groupId: number }) {
  const [location, setLocation] = useState<Location | null>(null);
  const [radius, setRadius] = useState(50);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Location>(`/groups/${groupId}/location`)
      .then(setLocation)
      .catch((err) => setMessage({ ok: false, text: errorText(err) }));
  }, [groupId]);

  async function setHere() {
    setBusy(true);
    setMessage(null);
    const coords = await getCurrentCoords(15000);
    if (!coords) {
      setBusy(false);
      setMessage({ ok: false, text: 'Poloha není dostupná. Povolte ji v prohlížeči (vyžaduje HTTPS nebo localhost).' });
      return;
    }
    try {
      setLocation(
        await api<Location>(`/groups/${groupId}/location`, {
          method: 'PUT',
          json: { latitude: coords.latitude, longitude: coords.longitude, radius_m: radius },
        }),
      );
      setMessage({ ok: true, text: `Učebna nastavena, studenti musí být do ${radius} m od tohoto místa.` });
    } catch (err) {
      setMessage({ ok: false, text: errorText(err) });
    } finally {
      setBusy(false);
    }
  }

  async function clear() {
    setBusy(true);
    try {
      setLocation(await api<Location>(`/groups/${groupId}/location`, { method: 'DELETE' }));
      setMessage({ ok: true, text: 'Ověřování polohy vypnuto.' });
    } catch (err) {
      setMessage({ ok: false, text: errorText(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <details>
      <summary>
        Poloha učebny{' '}
        <span className="muted small">{location?.enabled ? `(zapnuto, ${location.radius_m} m)` : '(vypnuto)'}</span>
      </summary>
      <div className="stack">
        <p className="muted small">
          Nastavte, když jste ve třídě. Studenti pak mohou zapsat docházku jen uvnitř této oblasti. Souřadnice
          studentů se neukládají.
        </p>
        <label>
          Poloměr (m)
          <input type="number" min={10} max={1000} value={radius} onChange={(e) => setRadius(Number(e.target.value))} />
        </label>
        <div className="row wrap">
          <button className="primary" disabled={busy} onClick={setHere}>Nastavit podle mé polohy</button>
          {location?.enabled && <button disabled={busy} onClick={clear}>Vypnout ověřování</button>}
        </div>
        {message && <p className={message.ok ? 'success' : 'error'} role="status">{message.text}</p>}
      </div>
    </details>
  );
}
