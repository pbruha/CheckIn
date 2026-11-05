"""Registrace zařízení pro Web Push upozornění."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import get_current_user, get_db, get_now, get_settings
from ..models import PushSubscription, User
from ..push import push_enabled

router = APIRouter(tags=["push"])


class Keys(BaseModel):
    p256dh: str
    auth: str


class SubscriptionIn(BaseModel):
    endpoint: str
    keys: Keys


class EndpointIn(BaseModel):
    endpoint: str


@router.get("/push/public-key")
def public_key(settings: Settings = Depends(get_settings)) -> dict:
    # Bez konfigurace vrací null (ne 404), aby se každá stránka nehlásila jako chyba v konzoli.
    return {"public_key": settings.vapid_public_key if push_enabled(settings) else None}


@router.post("/me/push-subscriptions", status_code=201)
def subscribe(
    body: SubscriptionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> dict:
    if not body.endpoint.startswith("https://"):
        raise HTTPException(status_code=422, detail="Odběr musí mít HTTPS endpoint")
    sub = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint))
    if sub is None:
        sub = PushSubscription(endpoint=body.endpoint, created_at=now)
        db.add(sub)
    sub.user_id = user.id
    sub.p256dh = body.keys.p256dh
    sub.auth = body.keys.auth
    db.commit()
    return {"subscribed": True}


@router.delete("/me/push-subscriptions")
def unsubscribe(body: EndpointIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    sub = db.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == body.endpoint, PushSubscription.user_id == user.id)
    )
    if sub is not None:
        db.delete(sub)
        db.commit()
    return {"subscribed": False}
