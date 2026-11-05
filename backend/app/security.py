"""Hesla, podepsané tokeny a rotující QR/číselné kódy. Vše jen standardní knihovna."""

from __future__ import annotations

import base64
import calendar
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta

PBKDF2_ITERATIONS = 200_000


def to_epoch(dt: datetime) -> int:
    """Převod naivního UTC datetime na epochu (bez závislosti na lokální časové zóně)."""
    return calendar.timegm(dt.timetuple())


def _sign(key: str, message: str) -> str:
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


# --- hesla -----------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
    return hmac.compare_digest(digest.hex(), digest_hex)


# --- přihlašovací token ----------------------------------------------------

def make_auth_token(key: str, user_id: int, role: str, now: datetime, ttl_hours: int) -> str:
    payload = {"uid": user_id, "role": role, "exp": to_epoch(now + timedelta(hours=ttl_hours))}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{body}.{_sign(key, body)}"


def read_auth_token(key: str, token: str, now: datetime) -> dict | None:
    try:
        body, signature = token.rsplit(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(_sign(key, body), signature):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get("exp", 0) < to_epoch(now):
        return None
    return payload


# --- rotující QR kód -------------------------------------------------------

def current_window(now: datetime, window_seconds: int) -> int:
    return to_epoch(now) // window_seconds


def make_qr_token(key: str, session_id: int, window: int) -> str:
    signature = _sign(key, f"qr:{session_id}:{window}")[:32]
    return f"{session_id}.{window}.{signature}"


def check_qr_token(key: str, token: str, session_id: int, now: datetime, window_seconds: int) -> bool:
    """Token platí v aktuálním a předchozím okně, aby stihl pomalejší telefon/síť."""
    try:
        sid_str, window_str, signature = token.split(".")
        token_session, token_window = int(sid_str), int(window_str)
    except ValueError:
        return False
    if token_session != session_id:
        return False
    if token_window not in (current_window(now, window_seconds), current_window(now, window_seconds) - 1):
        return False
    expected = _sign(key, f"qr:{token_session}:{token_window}")[:32]
    return hmac.compare_digest(expected, signature)


def qr_seconds_left(now: datetime, window_seconds: int) -> int:
    return window_seconds - (to_epoch(now) % window_seconds)


# --- číselný kód, otisk zařízení -------------------------------------------

def new_numeric_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def hash_device(key: str, device_id: str) -> str:
    """Otisk zařízení – HMAC, takže z databáze nejde zpětně zjistit identifikátor zařízení."""
    return _sign(key, f"device:{device_id}")


# --- krátkodobý podepsaný stav (SSO: state, nonce, PKCE verifier) -----------

def make_signed(key: str, payload: dict, now: datetime, ttl_seconds: int) -> str:
    data = dict(payload, exp=to_epoch(now) + ttl_seconds)
    body = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{body}.{_sign(key, body)}"


def read_signed(key: str, token: str, now: datetime) -> dict | None:
    return read_auth_token(key, token, now)
