export const CHECKIN_PATH = '/student/checkin';

/** Obsah QR kódu: odkaz, který po naskenování otevře check-in v aplikaci. */
export function buildCheckinUrl(origin: string, sessionId: number, qrToken: string): string {
  const url = new URL(CHECKIN_PATH, origin);
  url.searchParams.set('s', String(sessionId));
  url.searchParams.set('t', qrToken);
  return url.toString();
}

/** Z textu naskenovaného QR kódu vytáhne ID hodiny a token; jinak null. */
export function parseCheckinUrl(text: string): { sessionId: number; qrToken: string } | null {
  try {
    const url = new URL(text);
    if (url.pathname !== CHECKIN_PATH) return null;
    const sessionId = Number(url.searchParams.get('s'));
    const qrToken = url.searchParams.get('t') ?? '';
    if (!Number.isInteger(sessionId) || sessionId <= 0 || !qrToken) return null;
    return { sessionId, qrToken };
  } catch {
    return null;
  }
}
