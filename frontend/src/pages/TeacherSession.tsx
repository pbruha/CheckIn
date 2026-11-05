import { useCallback, useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { QRCodeSVG } from 'qrcode.react';
import { api } from '../lib/api';
import { buildCheckinUrl } from '../lib/checkinUrl';
import { errorText } from '../lib/errors';
import { formatDateTime, formatTime, statusLabel, METHOD_LABELS } from '../lib/format';
import type { LiveAttendance, QrInfo } from '../lib/types';

const LIVE_INTERVAL_MS = 3000;
const QR_INTERVAL_MS = 4000; // QR se mění každých 15 s, token platí i v předchozím okně

const EDITABLE = ['present', 'late', 'absent', 'excused'] as const;

export function TeacherSession() {
  const { id } = useParams();
  const sessionId = Number(id);
  const [live, setLive] = useState<LiveAttendance | null>(null);
  const [qr, setQr] = useState<QrInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const status = live?.session.status;

  const loadLive = useCallback(
    () =>
      api<LiveAttendance>(`/sessions/${sessionId}/attendance`)
        .then(setLive)
        .catch((err) => setError(errorText(err))),
    [sessionId],
  );

  useEffect(() => {
    loadLive();
  }, [loadLive]);

  // Živý přehled: obnovuje se, dokud hodina neskončila.
  useEffect(() => {
    if (!status || status === 'closed') return;
    const timer = setInterval(loadLive, LIVE_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [status, loadLive]);

  // Rotující QR kód: jen když docházka běží.
  useEffect(() => {
    if (status !== 'running') {
      setQr(null);
      return;
    }
    const fetchQr = () =>
      api<QrInfo>(`/sessions/${sessionId}/qr`)
        .then(setQr)
        .catch((err) => setError(errorText(err)));
    fetchQr();
    const timer = setInterval(fetchQr, QR_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [status, sessionId]);

  async function runAction(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await loadLive();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(userId: number, newStatus: string) {
    await runAction(() =>
      api(`/sessions/${sessionId}/attendance/${userId}`, { method: 'PUT', json: { status: newStatus } }),
    );
  }

  if (!live) {
    return error ? <p className="error" role="alert">{error}</p> : <p className="muted">Načítání…</p>;
  }

  const { session, counts, students } = live;
  const present = (counts.present ?? 0) + (counts.late ?? 0);

  return (
    <div className="stack-lg">
      <p className="muted">
        {formatDateTime(session.starts_at)} – {formatTime(session.ends_at)} ·{' '}
        <strong>{statusLabel(session.status)}</strong>
      </p>
      {error && <p className="error" role="alert">{error}</p>}

      {session.status === 'ready' && (
        <div className="card">
          <p>Docházka ještě není spuštěna.</p>
          <button className="primary" disabled={busy} onClick={() => runAction(() => api(`/sessions/${sessionId}/start`, { method: 'POST' }))}>
            Spustit docházku
          </button>
        </div>
      )}

      {session.status === 'running' && (
        <section className="card checkin-screen">
          {qr ? (
            <>
              <div className="qr-box">
                <QRCodeSVG
                  value={buildCheckinUrl(window.location.origin, sessionId, qr.qr_token)}
                  size={260}
                  includeMargin
                  aria-label="QR kód pro zápis docházky"
                />
              </div>
              <div className="code-box">
                <span className="muted small">Číselný kód (obnoví se za {qr.code_expires_in} s)</span>
                <strong className="code">{qr.code}</strong>
              </div>
            </>
          ) : (
            <p className="muted">Načítání QR kódu…</p>
          )}
          <p className="muted small">QR kód se mění každých 15 sekund. Snímek obrazovky nepomůže.</p>
          <button
            className="danger"
            disabled={busy}
            onClick={() => {
              if (window.confirm('Opravdu ukončit docházku? Chybějící studenti dostanou nepřítomnost.')) {
                runAction(() => api(`/sessions/${sessionId}/close`, { method: 'POST' }));
              }
            }}
          >
            Ukončit docházku
          </button>
        </section>
      )}

      <section className="stack">
        <p>
          Přítomno: <strong>{present}</strong> z {students.length} · pozdě: {counts.late ?? 0} · nepřítomno:{' '}
          {counts.absent ?? 0} · omluveno: {counts.excused ?? 0}
          {session.status !== 'closed' && counts.none ? ` · zatím nezapsáno: ${counts.none}` : ''}
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Student</th>
                <th>Stav</th>
                <th>Způsob</th>
                <th>Čas</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.user_id}>
                  <td>
                    {s.name || s.email}
                    <div className="muted small">{s.email}</div>
                  </td>
                  <td>
                    <select
                      aria-label={`Stav studenta ${s.name || s.email}`}
                      value={s.status}
                      disabled={busy}
                      onChange={(e) => changeStatus(s.user_id, e.target.value)}
                    >
                      {s.status === 'none' && <option value="none">Nezapsán</option>}
                      {EDITABLE.map((st) => (
                        <option key={st} value={st}>{statusLabel(st)}</option>
                      ))}
                    </select>
                  </td>
                  <td>{s.method ? METHOD_LABELS[s.method] ?? s.method : '—'}</td>
                  <td>{s.recorded_at ? formatTime(s.recorded_at) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Link to={`/teacher/groups/${session.group_id}/stats`}>Statistiky skupiny →</Link>
      </section>
    </div>
  );
}
