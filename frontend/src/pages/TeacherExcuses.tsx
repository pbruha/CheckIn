import { useEffect, useState } from 'react';
import { api, downloadFile } from '../lib/api';
import { errorText } from '../lib/errors';
import { formatDateTime, formatTime } from '../lib/format';
import type { ManagedExcuse } from '../lib/types';

type Filter = 'pending' | 'approved' | 'rejected';
const FILTERS: { value: Filter; label: string }[] = [
  { value: 'pending', label: 'Ke schválení' },
  { value: 'approved', label: 'Schválené' },
  { value: 'rejected', label: 'Zamítnuté' },
];

export function TeacherExcuses() {
  const [filter, setFilter] = useState<Filter>('pending');
  const [items, setItems] = useState<ManagedExcuse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    setItems(null);
    api<ManagedExcuse[]>(`/excuses?status=${filter}`)
      .then(setItems)
      .catch((err) => setError(errorText(err)));
  }, [filter, reload]);

  return (
    <div className="stack-lg">
      <div className="row wrap" role="tablist">
        {FILTERS.map((f) => (
          <button key={f.value} className={filter === f.value ? 'primary' : ''} onClick={() => setFilter(f.value)}>
            {f.label}
          </button>
        ))}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {items === null && !error && <p className="muted">Načítání…</p>}
      {items !== null && items.length === 0 && <p className="muted">Žádné omluvenky v tomto stavu.</p>}
      {items?.map((ex) => (
        <ExcuseCard key={ex.id} excuse={ex} onDecided={() => setReload((r) => r + 1)} />
      ))}
    </div>
  );
}

function ExcuseCard({ excuse, onDecided }: { excuse: ManagedExcuse; onDecided: () => void }) {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function decide(decision: 'approve' | 'reject') {
    setBusy(true);
    setError(null);
    try {
      await api(`/excuses/${excuse.id}/decision`, { method: 'POST', json: { decision, note: note || null } });
      onDecided();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card stack">
      <div className="row between wrap">
        <strong>{excuse.student.name || excuse.student.email}</strong>
        <span className="muted small">{excuse.group.name} · {formatDateTime(excuse.session.starts_at)}–{formatTime(excuse.session.ends_at)}</span>
      </div>
      <p>{excuse.text}</p>
      {excuse.has_attachment && (
        <button className="link" onClick={() => downloadFile(`/excuses/${excuse.id}/attachment`, excuse.attachment_name ?? 'priloha').catch((err) => setError(errorText(err)))}>
          Stáhnout přílohu ({excuse.attachment_name})
        </button>
      )}
      {excuse.status === 'pending' ? (
        <>
          <input placeholder="Poznámka (nepovinná)" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="row wrap">
            <button className="primary" disabled={busy} onClick={() => decide('approve')}>Schválit</button>
            <button className="danger" disabled={busy} onClick={() => decide('reject')}>Zamítnout</button>
          </div>
        </>
      ) : (
        <p className="small muted">
          {excuse.status === 'approved' ? 'Schváleno' : 'Zamítnuto'} {excuse.decided_at && formatDateTime(excuse.decided_at)}
          {excuse.decision_note ? ` – ${excuse.decision_note}` : ''}
        </p>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}
