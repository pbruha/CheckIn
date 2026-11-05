"""Endpointy přihlášení školním účtem: /auth/sso/config, /auth/sso/login, /auth/sso/callback."""

from __future__ import annotations

import secrets
from datetime import datetime
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import get_db, get_now, get_settings
from ..models import User
from ..security import make_auth_token, make_signed, read_signed
from ..sso import (
    SSOError,
    build_authorize_url,
    exchange_code,
    fetch_discovery,
    new_pkce_pair,
    verify_id_token,
)

router = APIRouter(prefix="/auth/sso", tags=["sso"])

STATE_COOKIE = "checkin_sso"
STATE_TTL = 600


def _enabled(settings: Settings) -> bool:
    return bool(settings.oidc_issuer and settings.oidc_client_id and settings.oidc_redirect_uri)


def _http(request: Request) -> httpx.Client:
    return httpx.Client(transport=getattr(request.app.state, "http_transport", None), follow_redirects=False)


def _fail(settings: Settings, message: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.frontend_url}/login#sso_error={quote(message)}", status_code=303)


@router.get("/config")
def sso_config(settings: Settings = Depends(get_settings)) -> dict:
    return {"enabled": _enabled(settings), "password_login": settings.sso_password_login}


@router.get("/login")
def sso_login(request: Request, settings: Settings = Depends(get_settings), now: datetime = Depends(get_now)):
    if not _enabled(settings):
        raise HTTPException(status_code=404, detail="Školní přihlášení není nastaveno")
    with _http(request) as client:
        discovery = fetch_discovery(client, settings.oidc_issuer)
    verifier, challenge = new_pkce_pair()
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    url = build_authorize_url(
        discovery, settings.oidc_client_id, settings.oidc_redirect_uri, settings.oidc_scopes, state, nonce, challenge
    )
    response = RedirectResponse(url, status_code=303)
    cookie = make_signed(
        settings.secret_key, {"state": state, "nonce": nonce, "verifier": verifier}, now, STATE_TTL
    )
    response.set_cookie(
        STATE_COOKIE,
        cookie,
        max_age=STATE_TTL,
        httponly=True,
        samesite="lax",
        secure=settings.oidc_redirect_uri.startswith("https://"),
        path="/",  # callback může být za reverzní proxy pod /api, cookie proto nemá užší cestu
    )
    return response


@router.get("/callback")
def sso_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
):
    if not _enabled(settings):
        raise HTTPException(status_code=404, detail="Školní přihlášení není nastaveno")
    if error:
        return _fail(settings, "Přihlášení bylo zrušeno")
    saved = read_signed(settings.secret_key, request.cookies.get(STATE_COOKIE, ""), now)
    if saved is None or not state or not code or not secrets.compare_digest(saved["state"], state):
        return _fail(settings, "Přihlášení vypršelo, zkuste to znovu")

    try:
        with _http(request) as client:
            discovery = fetch_discovery(client, settings.oidc_issuer)
            id_token = exchange_code(
                client, discovery, code, settings.oidc_redirect_uri,
                settings.oidc_client_id, settings.oidc_client_secret, saved["verifier"],
            )
            claims = verify_id_token(client, discovery, id_token, settings.oidc_client_id, saved["nonce"])
    except SSOError as exc:
        return _fail(settings, str(exc))

    email = str(claims.get("email") or claims.get("preferred_username") or "").strip().lower()
    if not email or "@" not in email:
        return _fail(settings, "Účet nemá e-mailovou adresu")
    if claims.get("email_verified") is False:
        return _fail(settings, "E-mailová adresa účtu není ověřena")
    domain = email.rsplit("@", 1)[1]
    if settings.sso_allowed_domain and domain != settings.sso_allowed_domain:
        return _fail(settings, "Tento účet nemá přístup do aplikace")

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        name = claims.get("name") or " ".join(
            p for p in (claims.get("given_name"), claims.get("family_name")) if p
        )
        user = User(email=email, name=name or "", role="student", password_hash=None)
        db.add(user)
        db.commit()
    token = make_auth_token(settings.secret_key, user.id, user.role, now, settings.token_ttl_hours)

    response = RedirectResponse(f"{settings.frontend_url}/login#token={token}", status_code=303)
    response.delete_cookie(STATE_COOKIE, path="/")
    return response
