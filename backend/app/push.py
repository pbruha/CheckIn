"""Web Push (VAPID): odesílání upozornění na zařízení uživatelů.

Odesílání běží na pozadí (BackgroundTasks) a chyby se jen zapisují do logu – selhání
notifikace nesmí shodit požadavek. Odběr, který push služba označí jako neplatný (404/410), se smaže.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .config import Settings
from .models import PushSubscription

log = logging.getLogger("checkin.push")

Sender = Callable[[dict, str, Settings], None]


def push_enabled(settings: Settings) -> bool:
    return bool(settings.vapid_private_key and settings.vapid_public_key)


def default_sender(subscription_info: dict, data: str, settings: Settings) -> None:
    from py_vapid import Vapid01
    from pywebpush import webpush

    # PEM se předává jako objekt Vapid01 – řetězec by pywebpush bral jako base64 DER a selhal.
    vapid = Vapid01.from_pem(settings.vapid_private_key.encode())
    webpush(
        subscription_info=subscription_info,
        data=data,
        vapid_private_key=vapid,
        vapid_claims={"sub": settings.vapid_subject},
        ttl=3600,
    )


def notify_users(
    session_factory: sessionmaker,
    settings: Settings,
    sender: Sender,
    user_ids: list[int],
    title: str,
    body: str,
    url: str = "/",
) -> None:
    if not push_enabled(settings) or not user_ids:
        return
    payload = json.dumps({"title": title, "body": body, "url": url})
    with session_factory() as db:
        subscriptions = db.scalars(
            select(PushSubscription).where(PushSubscription.user_id.in_(user_ids))
        ).all()
        for sub in subscriptions:
            info = {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}
            try:
                sender(info, payload, settings)
            except Exception as exc:  # noqa: BLE001 – chyba jedné notifikace nesmí zastavit ostatní
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status in (404, 410):
                    db.delete(sub)
                else:
                    log.warning("Web Push se nepodařilo odeslat: %s", exc)
        db.commit()
