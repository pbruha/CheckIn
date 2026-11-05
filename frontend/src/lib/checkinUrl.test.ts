import { describe, expect, it } from 'vitest';
import { buildCheckinUrl, parseCheckinUrl } from './checkinUrl';

describe('QR odkaz pro check-in', () => {
  it('sestaví odkaz, který se dá zase rozparsovat', () => {
    const url = buildCheckinUrl('https://checkin.skola.cz', 42, '42.1000.abcdef');
    expect(url).toBe('https://checkin.skola.cz/student/checkin?s=42&t=42.1000.abcdef');
    expect(parseCheckinUrl(url)).toEqual({ sessionId: 42, qrToken: '42.1000.abcdef' });
  });

  it('odmítne cizí QR kódy a neúplné odkazy', () => {
    expect(parseCheckinUrl('https://example.com/neco')).toBeNull();
    expect(parseCheckinUrl('https://checkin.skola.cz/student/checkin?s=abc&t=x')).toBeNull();
    expect(parseCheckinUrl('https://checkin.skola.cz/student/checkin?s=3')).toBeNull();
    expect(parseCheckinUrl('neplatny text')).toBeNull();
  });
});
