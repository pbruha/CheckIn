export const STATUS_LABELS: Record<string, string> = {
  present: 'Přítomen',
  late: 'Pozdě',
  absent: 'Nepřítomen',
  excused: 'Omluven',
  none: 'Nezapsán',
  ready: 'Připravena',
  running: 'Probíhá',
  closed: 'Uzavřena',
};

export const METHOD_LABELS: Record<string, string> = {
  qr: 'QR kód',
  code: 'Kód',
  manual: 'Ručně',
  auto: 'Automaticky',
};

export function statusLabel(status: string | null | undefined): string {
  if (!status) return 'Nezapsán';
  return STATUS_LABELS[status] ?? status;
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('cs-CZ', { dateStyle: 'short', timeStyle: 'short' });
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('cs-CZ', { hour: '2-digit', minute: '2-digit' });
}

export function isSameLocalDay(iso: string, reference: Date = new Date()): boolean {
  const d = new Date(iso);
  return (
    d.getFullYear() === reference.getFullYear() &&
    d.getMonth() === reference.getMonth() &&
    d.getDate() === reference.getDate()
  );
}

/** Hodnota pro <input type="datetime-local"> v lokálním čase. */
export function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
