import { api } from './api';

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padded = base64.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(base64.length / 4) * 4, '=');
  const raw = atob(padded);
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

/** Podpora Web Push v prohlížeči (vyžaduje service worker, tedy produkční build na HTTPS). */
export async function pushSupport(): Promise<{ supported: boolean; publicKey?: string }> {
  if (typeof window === 'undefined' || !('serviceWorker' in navigator) || !('PushManager' in window)) {
    return { supported: false };
  }
  try {
    const registration = await navigator.serviceWorker.getRegistration();
    if (!registration) return { supported: false };
    const { public_key } = await api<{ public_key: string | null }>('/push/public-key');
    return public_key ? { supported: true, publicKey: public_key } : { supported: false };
  } catch {
    return { supported: false }; // server nemá VAPID nebo není přihlášen
  }
}

export async function currentSubscription(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}

export async function enablePush(publicKey: string): Promise<void> {
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new Error('Upozornění nebyla povolena v prohlížeči');
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey),
  });
  const json = subscription.toJSON();
  await api('/me/push-subscriptions', {
    method: 'POST',
    json: { endpoint: json.endpoint, keys: { p256dh: json.keys?.p256dh, auth: json.keys?.auth } },
  });
}

export async function disablePush(): Promise<void> {
  const subscription = await currentSubscription();
  if (!subscription) return;
  await api('/me/push-subscriptions', { method: 'DELETE', json: { endpoint: subscription.endpoint } });
  await subscription.unsubscribe();
}
