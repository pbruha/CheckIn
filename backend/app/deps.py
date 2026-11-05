from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from .config import Settings
from .models import Group, User
from .security import read_auth_token


def get_db(request: Request) -> Iterator[Session]:
    db = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_now(request: Request) -> datetime:
    return request.app.state.clock()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Chybí přihlášení")
    payload = read_auth_token(settings.secret_key, authorization[len("Bearer "):], now)
    if payload is None:
        raise HTTPException(status_code=401, detail="Přihlášení vypršelo nebo je neplatné")
    user = db.get(User, payload["uid"])
    if user is None:
        raise HTTPException(status_code=401, detail="Uživatel neexistuje")
    return user


def require_teacher(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="Vyžadována role vyučující")
    return user


def ensure_can_manage_group(user: User, group: Group) -> None:
    """Vyučující spravuje jen své skupiny; administrátor všechny."""
    if user.role != "admin" and group.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Tuto skupinu spravuje jiný vyučující")
