export type Coords = { latitude: number; longitude: number; accuracy_m: number };

/**
 * Aktuální poloha, nebo null, pokud ji prohlížeč nedá (zamítnutí, timeout, bez GPS).
 * Vyžaduje HTTPS nebo localhost; poloha se nikam neukládá, slouží jen k ověření.
 */
export function getCurrentCoords(timeoutMs = 10000): Promise<Coords | null> {
  if (typeof navigator === 'undefined' || !navigator.geolocation) return Promise.resolve(null);
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy_m: pos.coords.accuracy,
        }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 0 },
    );
  });
}
