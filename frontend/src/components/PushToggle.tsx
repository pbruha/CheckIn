import { useEffect, useState } from 'react';
import { currentSubscription, disablePush, enablePush, pushSupport } from '../lib/push';
import { errorText } from '../lib/errors';

/** Přepínač upozornění na mobilu/počítači. Nezobrazí se, pokud prohlížeč nebo server push nepodporují. */
export function PushToggle() {
  const [state, setState] = useState<{ supported: boolean; publicKey?: string; enabled: boolean } | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    pushSupport().then(async (support) => {
      if (!support.supported) return setState({ supported: false, enabled: false });
      const sub = await currentSubscription().catch(() => null);
      setState({ supported: true, publicKey: support.publicKey, enabled: !!sub });
    });
  }, []);

  if (!state?.supported || !state.publicKey) return null;

  async function toggle() {
    setBusy(true);
    setMessage(null);
    try {
      if (state!.enabled) {
        await disablePush();
        setState({ ...state!, enabled: false });
      } else {
        await enablePush(state!.publicKey!);
        setState({ ...state!, enabled: true });
      }
    } catch (err) {
      setMessage(errorText(err, 'Upozornění se nepodařilo nastavit'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="push-toggle">
      <button onClick={toggle} disabled={busy}>
        {state.enabled ? 'Vypnout upozornění v zařízení' : 'Zapnout upozornění v zařízení'}
      </button>
      {message && <span className="error small"> {message}</span>}
    </div>
  );
}
