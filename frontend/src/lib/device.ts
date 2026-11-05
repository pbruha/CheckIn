const DEVICE_KEY = 'checkin.device';

function randomId(): string {
  // crypto.randomUUID je dostupné jen v zabezpečeném kontextu (HTTPS/localhost),
  // na síti přes http je tedy nutná záloha.
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return Array.from({ length: 4 }, () => Math.random().toString(36).slice(2, 10)).join('-');
}

/** Identifikátor zařízení pro kontrolu „jedno zařízení = jeden student“. */
export function getDeviceId(): string {
  try {
    const existing = localStorage.getItem(DEVICE_KEY);
    if (existing && existing.length >= 8) return existing;
    const id = randomId();
    localStorage.setItem(DEVICE_KEY, id);
    return id;
  } catch {
    return randomId();
  }
}
