"""OpenID Connect (authorization code + PKCE) pro přihlášení školním účtem.

Funguje s libovolným OIDC poskytovatelem (Azure AD, Google Workspace, Keycloak, …),
který má standardní discovery dokument. SAML zde není.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from urllib.parse import urlencode

import httpx
import jwt


class SSOError(Exception):
    """Chyba přihlášení – zpráva je bezpečná k zobrazení uživateli."""


def fetch_discovery(client: httpx.Client, issuer: str) -> dict:
    try:
        res = client.get(issuer.rstrip("/") + "/.well-known/openid-configuration", timeout=10)
        res.raise_for_status()
        doc = res.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SSOError("Školní přihlášení není dostupné") from exc
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri", "issuer"):
        if key not in doc:
            raise SSOError("Neplatný discovery dokument poskytovatele")
    return doc


def new_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def build_authorize_url(
    discovery: dict, client_id: str, redirect_uri: str, scopes: str, state: str, nonce: str, challenge: str
) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{discovery['authorization_endpoint']}?{query}"


def exchange_code(
    client: httpx.Client,
    discovery: dict,
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str | None,
    verifier: str,
) -> str:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    if client_secret:
        data["client_secret"] = client_secret
    try:
        res = client.post(discovery["token_endpoint"], data=data, timeout=10)
        res.raise_for_status()
        id_token = res.json().get("id_token")
    except (httpx.HTTPError, ValueError) as exc:
        raise SSOError("Výměna přihlašovacího kódu selhala") from exc
    if not id_token:
        raise SSOError("Poskytovatel nevrátil identitu uživatele")
    return id_token


def verify_id_token(client: httpx.Client, discovery: dict, id_token: str, client_id: str, nonce: str) -> dict:
    """Ověří podpis (JWKS), vydavatele, příjemce, expiraci a nonce."""
    try:
        header = jwt.get_unverified_header(id_token)
        jwks = client.get(discovery["jwks_uri"], timeout=10).json()
        keys = jwks.get("keys", [])
        key_data = next((k for k in keys if k.get("kid") == header.get("kid")), keys[0] if keys else None)
        if key_data is None:
            raise SSOError("Podpisový klíč poskytovatele nebyl nalezen")
        key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=discovery["issuer"],
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except SSOError:
        raise
    except (jwt.PyJWTError, httpx.HTTPError, ValueError, StopIteration, KeyError) as exc:
        raise SSOError("Ověření identity selhalo") from exc
    if claims.get("nonce") != nonce:
        raise SSOError("Ověření identity selhalo (nonce)")
    return claims
