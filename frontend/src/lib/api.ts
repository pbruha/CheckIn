const TOKEN_KEY = 'checkin.token';
export const UNAUTHORIZED_EVENT = 'checkin:unauthorized';

// localStorage může být nedostupný (privátní okno, blokované úložiště) – proto try/catch.
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* bez úložiště se uživatel jen přihlásí znovu */
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export type ApiInit = Omit<RequestInit, 'body'> & { json?: unknown; body?: BodyInit };

async function errorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === 'string') return data.detail;
    if (Array.isArray(data?.detail)) return data.detail.map((d: { msg: string }) => d.msg).join('; ');
  } catch {
    /* tělo není JSON */
  }
  return res.statusText || `Chyba ${res.status}`;
}

export async function api<T>(path: string, init: ApiInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  let body = init.body;
  if (init.json !== undefined) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(init.json);
  }
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const res = await fetch(`/api${path}`, { ...init, headers, body });
  if (!res.ok) {
    if (res.status === 401 && token) window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    throw new ApiError(res.status, await errorMessage(res));
  }
  return (await res.json()) as T;
}

/** Stažení souboru (CSV, příloha) s hlavičkou Authorization – obyčejný odkaz by token neposlal. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const token = getToken();
  const res = await fetch(`/api${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export const downloadCsv = downloadFile;
