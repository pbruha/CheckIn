import { useEffect, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { errorText } from '../lib/errors';
import { formatDateTime } from '../lib/format';
import type { Excuse, MyAttendance } from '../lib/types';

const EXCUSE_LABELS: Record<Excuse['status'], string> = {
  pending: 'Čeká na schválení',
  approved: 'Schváleno',
  rejected: 'Zamítnuto',
};

const ACCEPT = 'application/pdf,image/png,image/jpeg';

export function StudentExcuses() {
  const [params] = useSearchParams();
  const preselected = Number(params.get('session')) || null;
  const [sessions, setSessions] = useState<MyAttendance['items'] | null>(null);
  const [excuses, setExcuses] = useState<Excuse[]>([]);
  const [sessionId, setSessionId] = useState<number | null>(preselected);
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    api<MyAttendance>('/me/attendance')
      .then((data) => {
        // Omluvit lze hodinu, na které student není zapsán jako přítomen.
        const eligible = data.items.filter((i) => i.status !== 'present' && i.status !== 'late' && i.status !== 'excused');
        setSessions(eligible);
        setSessionId((current) => current ?? eligible[0]?.session_id ?? null);
      })
      .catch((err) => setMessage({ ok: false, text: errorText(err) }));
  }, []);

  useEffect(() => {
    api<Excuse[]>('/me/excuses')
      .then(setExcuses)
      .catch((err) => setMessage({ ok: false, text: errorText(err) }));
  }, [reload]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (sessionId === null) return;
    setBusy(true);
    setMessage(null);
    try {
      const form = new FormData();
      form.append('text', text);
      if (file) form.append('file', file);
      await api(`/sessions/${sessionId}/excuses`, { method: 'POST', body: form });
      setText('');
      setFile(null);
      setMessage({ ok: true, text: 'Omluvenka byla odeslána.' });
      setReload((r) => r + 1);
    } catch (err) {
      setMessage({ ok: false, text: errorText(err) });
    } finally {
      setBusy(false);
    }
  }

  const alreadySent = new Set(excuses.filter((e) => e.status !== 'rejected').map((e) => e.session_id));
  const choices = (sessions ?? []).filter((s) => !alreadySent.has(s.session_id));

  return (
    <div className="stack-lg">
      <section className="card stack">
        <h2>Nová omluvenka</h2>
        {sessions === null && <p className="muted">Načítání…</p>}
        {sessions !== null && choices.length === 0 && <p className="muted">Nemáte žádnou hodinu, ke které by šlo omluvit.</p>}
        {choices.length > 0 && (
          <form onSubmit={onSubmit} className="stack">
            <label>
              Hodina
              <select value={sessionId ?? ''} onChange={(e) => setSessionId(Number(e.target.value))} required>
                {choices.map((s) => (
                  <option key={s.session_id} value={s.session_id}>
                    {s.group_name} – {formatDateTime(s.starts_at)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Důvod
              <textarea required minLength={3} maxLength={2000} rows={4} value={text} onChange={(e) => setText(e.target.value)} />
            </label>
            <label>
              Příloha (PDF, PNG nebo JPG, max. 5 MB)
              <input type="file" accept={ACCEPT} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
            <button type="submit" className="primary" disabled={busy || text.trim().length < 3}>
              {busy ? 'Odesílám…' : 'Odeslat omluvenku'}
            </button>
          </form>
        )}
        {message && <p className={message.ok ? 'success' : 'error'} role="status">{message.text}</p>}
      </section>

      <section className="stack">
        <h2>Moje omluvenky</h2>
        {excuses.length === 0 && <p className="muted">Zatím žádné.</p>}
        <ul className="list">
          {excuses.map((ex) => (
            <li key={ex.id} className="stack">
              <div className="row between wrap">
                <span className={`badge badge-excuse-${ex.status}`}>{EXCUSE_LABELS[ex.status]}</span>
                <span className="muted small">odesláno {formatDateTime(ex.created_at)}</span>
              </div>
              <p>{ex.text}</p>
              {ex.decision_note && <p className="small">Poznámka vyučujícího: {ex.decision_note}</p>}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
