import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { Html5Qrcode } from 'html5-qrcode';
import { api } from '../lib/api';
import { getDeviceId } from '../lib/device';
import { errorText } from '../lib/errors';
import { formatDateTime, statusLabel } from '../lib/format';
import { parseCheckinUrl } from '../lib/checkinUrl';
import type { MyAttendance, MyAttendanceItem } from '../lib/types';

type Result = { ok: boolean; text: string };

export function StudentCheckin() {
  const [params] = useSearchParams();
  const urlSession = params.get('s');
  const urlToken = params.get('t');

  const [deviceId] = useState(getDeviceId);
  const [running, setRunning] = useState<MyAttendanceItem[] | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [code, setCode] = useState('');
  const [sessionChoice, setSessionChoice] = useState<number | null>(null);
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const autoSubmitted = useRef(false);

  async function submit(body: { session_id: number; qr_token?: string; code?: string }) {
    setBusy(true);
    setResult(null);
    try {
      const record = await api<{ status: string }>('/attendance/checkin', {
        method: 'POST',
        json: { ...body, device_id: deviceId },
      });
      setResult({ ok: true, text: `Docházka zapsána: ${statusLabel(record.status)}` });
    } catch (err) {
      setResult({ ok: false, text: errorText(err, 'Zápis se nepovedl') });
    } finally {
      setBusy(false);
    }
  }

  // Odkaz z naskenovaného QR kódu zapíše docházku automaticky (po přihlášení).
  useEffect(() => {
    if (urlSession && urlToken && !autoSubmitted.current) {
      autoSubmitted.current = true;
      submit({ session_id: Number(urlSession), qr_token: urlToken });
    }
  }, [urlSession, urlToken]);

  useEffect(() => {
    api<MyAttendance>('/me/attendance')
      .then((data) => {
        const open = data.items.filter((i) => i.session_status === 'running');
        setRunning(open);
        if (open.length > 0) setSessionChoice(open[0].session_id);
      })
      .catch(() => setRunning([]));
  }, []);

  useEffect(() => {
    return () => {
      const scanner = scannerRef.current;
      scannerRef.current = null;
      scanner?.stop().catch(() => {});
    };
  }, []);

  async function startScan() {
    setResult(null);
    setScanning(true);
    try {
      // Knihovna pro skenování se načte až při použití kamery (menší počáteční bundle).
      const { Html5Qrcode } = await import('html5-qrcode');
      const scanner = new Html5Qrcode('qr-reader');
      scannerRef.current = scanner;
      await scanner.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 240, height: 240 } },
        (text) => {
          const parsed = parseCheckinUrl(text);
          stopScan();
          if (parsed) submit({ session_id: parsed.sessionId, qr_token: parsed.qrToken });
          else setResult({ ok: false, text: 'Tento QR kód nepatří k docházce.' });
        },
        () => {},
      );
    } catch {
      setScanning(false);
      scannerRef.current = null;
      setResult({ ok: false, text: 'Kamera není dostupná. Potřebujete povolení kamery a HTTPS (nebo localhost).' });
    }
  }

  async function stopScan() {
    const scanner = scannerRef.current;
    scannerRef.current = null;
    setScanning(false);
    if (scanner) {
      try {
        await scanner.stop();
        scanner.clear();
      } catch {
        /* skener už nebyl spuštěn */
      }
    }
  }

  function onCodeSubmit(e: FormEvent) {
    e.preventDefault();
    if (sessionChoice === null) return;
    submit({ session_id: sessionChoice, code });
  }

  return (
    <div className="stack-lg">
      {result && (
        <p className={result.ok ? 'success' : 'error'} role="status">
          {result.text}
        </p>
      )}

      <section className="card stack">
        <h2>Naskenovat QR kód</h2>
        {/* Element musí existovat, i když skener neběží – do něj html5-qrcode vykresluje video. */}
        <div id="qr-reader" className="scanner" hidden={!scanning} />
        {scanning ? (
          <button onClick={stopScan}>Zrušit skenování</button>
        ) : (
          <button className="primary" disabled={busy} onClick={startScan}>Spustit kameru</button>
        )}
      </section>

      <section className="card stack">
        <h2>Zadat číselný kód</h2>
        {running === null && <p className="muted">Načítání…</p>}
        {running !== null && running.length === 0 && (
          <p className="muted">Právě neprobíhá žádná docházka.</p>
        )}
        {running !== null && running.length > 0 && (
          <form onSubmit={onCodeSubmit} className="stack">
            {running.length > 1 && (
              <label>
                Hodina
                <select value={sessionChoice ?? ''} onChange={(e) => setSessionChoice(Number(e.target.value))}>
                  {running.map((i) => (
                    <option key={i.session_id} value={i.session_id}>
                      {i.group_name} – {formatDateTime(i.starts_at)}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label>
              Kód (6 číslic)
              <input
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                required
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              />
            </label>
            <button type="submit" className="primary" disabled={busy || code.length !== 6}>Zapsat</button>
          </form>
        )}
      </section>
    </div>
  );
}
