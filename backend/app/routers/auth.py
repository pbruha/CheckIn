from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import get_current_user, get_db, get_now, get_settings
from ..models import User
from ..security import make_auth_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


def serialize_user(user: User) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


@router.post("/login")
def login(
    body: LoginIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
) -> dict:
    if settings.oidc_issuer and not settings.sso_password_login:
        raise HTTPException(status_code=403, detail="Přihlaste se prosím školním účtem")
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Neplatný e-mail nebo heslo")
    token = make_auth_token(settings.secret_key, user.id, user.role, now, settings.token_ttl_hours)
    return {"token": token, "user": serialize_user(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return serialize_user(user)
