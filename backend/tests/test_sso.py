from __future__ import annotations

import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import Settings
from app.main import create_app
from conftest import FakeClock, T0, login, make_user

ISSUER = "https://idp.test"
CLIENT_ID = "checkin-app"
REDIRECT = "http://testserver/auth/sso/callback"


class FakeIdP:
    """Minimální OIDC poskytovatel: discovery, JWKS a token endpoint."""

    def __init__(self):
        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.private.public_key()))
        public_jwk.update({"kid": "k1", "use": "sig", "alg": "RS256"})
        self.jwks = {"keys": [public_jwk]}
        self.id_token: str | None = None
        self.token_requests: list[dict] = []

    def make_id_token(self, nonce: str, email: str = "alice@skola.cz", **overrides) -> str:
        now = int(time.time())
        claims = {
            "iss": ISSUER, "aud": CLIENT_ID, "sub": "abc-123", "iat": now, "exp": now + 300,
            "nonce": nonce, "email": email, "email_verified": True, "name": "Alice Nováková",
        }
        claims.update(overrides)
        return jwt.encode(claims, self.private, algorithm="RS256", headers={"kid": "k1"})

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/.well-known/openid-configuration":
            return httpx.Response(200, json={
                "issuer": ISSUER,
                "authorization_endpoint": f"{ISSUER}/authorize",
                "token_endpoint": f"{ISSUER}/token",
                "jwks_uri": f"{ISSUER}/jwks",
            })
        if path == "/jwks":
            return httpx.Response(200, json=self.jwks)
        if path == "/token":
            self.token_requests.append(dict(parse_qs(request.content.decode())))
            return httpx.Response(200, json={"id_token": self.id_token, "token_type": "Bearer"})
        return httpx.Response(404)


@pytest.fixture
def idp():
    return FakeIdP()


@pytest.fixture
def sso_settings(tmp_path):
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'sso.db'}",
        secret_key="test-secret",
        oidc_issuer=ISSUER,
        oidc_client_id=CLIENT_ID,
        oidc_client_secret="s3cret",
        oidc_redirect_uri=REDIRECT,
        frontend_url="http://localhost:5173",
    )


@pytest.fixture
def sso_app(sso_settings, idp, clock):
    return create_app(settings=sso_settings, clock=clock, http_transport=httpx.MockTransport(idp.handler))


@pytest.fixture
def sso_client(sso_app):
    from fastapi.testclient import TestClient
    return TestClient(sso_app)


def start_login(client):
    r = client.get("/auth/sso/login", follow_redirects=False)
    assert r.status_code == 303, r.text
    target = urlparse(r.headers["location"])
    assert target.netloc == "idp.test" and target.path == "/authorize"
    params = {k: v[0] for k, v in parse_qs(target.query).items()}
    assert params["code_challenge_method"] == "S256" and params["client_id"] == CLIENT_ID
    return params["state"], params["nonce"]


def callback(client, code="code-1", state=None):
    return client.get(f"/auth/sso/callback?code={code}&state={state}", follow_redirects=False)


def token_from_redirect(location: str) -> str:
    assert location.startswith("http://localhost:5173/login#token="), location
    return location.split("#token=", 1)[1]


def test_sso_config_reports_enabled(sso_client):
    assert sso_client.get("/auth/sso/config").json() == {"enabled": True, "password_login": True}


def test_sso_disabled_without_issuer(client):
    assert client.get("/auth/sso/config").json()["enabled"] is False
    assert client.get("/auth/sso/login").status_code == 404


def test_full_login_creates_student_and_returns_token(sso_client, idp):
    state, nonce = start_login(sso_client)
    idp.id_token = idp.make_id_token(nonce)
    r = callback(sso_client, state=state)
    assert r.status_code == 303
    token = token_from_redirect(r.headers["location"])
    me = sso_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["email"] == "alice@skola.cz" and me["role"] == "student" and me["name"] == "Alice Nováková"
    # PKCE: vyměněný kód musí přijít se správným verifierem (token endpoint ho dostal)
    assert idp.token_requests[0]["grant_type"] == ["authorization_code"]
    assert idp.token_requests[0]["code_verifier"][0]


def test_existing_teacher_keeps_role_on_sso_login(sso_app, sso_client, idp):
    make_user(sso_app, "alice@skola.cz", "Alice", "teacher", password=None)
    state, nonce = start_login(sso_client)
    idp.id_token = idp.make_id_token(nonce)
    token = token_from_redirect(callback(sso_client, state=state).headers["location"])
    assert sso_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["role"] == "teacher"


def test_state_mismatch_is_rejected(sso_client, idp):
    _, nonce = start_login(sso_client)
    idp.id_token = idp.make_id_token(nonce)
    r = callback(sso_client, state="podvrzeny-stav")
    assert "#sso_error=" in r.headers["location"]
    assert "#token=" not in r.headers["location"]


def test_missing_state_cookie_is_rejected(sso_client, idp):
    r = sso_client.get("/auth/sso/callback?code=x&state=y", follow_redirects=False)
    assert "#sso_error=" in r.headers["location"]


def test_wrong_nonce_is_rejected(sso_client, idp):
    state, _ = start_login(sso_client)
    idp.id_token = idp.make_id_token("jiny-nonce")
    r = callback(sso_client, state=state)
    assert "#sso_error=" in r.headers["location"]


def test_wrong_audience_is_rejected(sso_client, idp):
    state, nonce = start_login(sso_client)
    idp.id_token = idp.make_id_token(nonce, aud="jina-aplikace")
    assert "#sso_error=" in callback(sso_client, state=state).headers["location"]


def test_expired_token_is_rejected(sso_client, idp):
    state, nonce = start_login(sso_client)
    idp.id_token = idp.make_id_token(nonce, exp=int(time.time()) - 60, iat=int(time.time()) - 400)
    assert "#sso_error=" in callback(sso_client, state=state).headers["location"]


def test_token_signed_by_other_key_is_rejected(sso_client, idp):
    state, nonce = start_login(sso_client)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode({"iss": ISSUER, "aud": CLIENT_ID, "sub": "x", "iat": int(time.time()),
                         "exp": int(time.time()) + 300, "nonce": nonce, "email": "admin@skola.cz"},
                        other, algorithm="RS256", headers={"kid": "k1"})
    idp.id_token = forged
    r = callback(sso_client, state=state)
    assert "#sso_error=" in r.headers["location"]
    assert "#token=" not in r.headers["location"]


def test_domain_restriction(sso_app, sso_settings, idp):
    from fastapi.testclient import TestClient
    sso_settings_restricted = sso_settings.__class__(**{**sso_settings.__dict__, "sso_allowed_domain": "fav.zcu.cz"})
    app = create_app(settings=sso_settings_restricted, clock=sso_app.state.clock,
                     http_transport=httpx.MockTransport(idp.handler))
    client = TestClient(app)
    state, nonce = start_login(client)
    idp.id_token = idp.make_id_token(nonce, email="alice@skola.cz")
    assert "#sso_error=" in callback(client, state=state).headers["location"]


def test_unverified_email_is_rejected(sso_client, idp):
    state, nonce = start_login(sso_client)
    idp.id_token = idp.make_id_token(nonce, email_verified=False)
    assert "#sso_error=" in callback(sso_client, state=state).headers["location"]


def test_state_is_single_use(sso_client, idp):
    state, nonce = start_login(sso_client)
    idp.id_token = idp.make_id_token(nonce)
    callback(sso_client, state=state)
    # cookie se po úspěchu smaže, druhé použití stejného stavu selže
    sso_client.cookies.clear()
    assert "#sso_error=" in callback(sso_client, state=state).headers["location"]


def test_password_login_still_works_with_sso_enabled(sso_app, sso_client):
    make_user(sso_app, "ucitel@skola.cz", "Jana", "teacher")
    headers = login(sso_client, "ucitel@skola.cz")
    assert sso_client.get("/auth/me", headers=headers).status_code == 200


def test_password_login_can_be_disabled_when_sso_is_on(sso_settings, idp, clock, sso_app):
    from fastapi.testclient import TestClient
    make_user(sso_app, "ucitel@skola.cz", "Jana", "teacher")
    locked = sso_settings.__class__(**{**sso_settings.__dict__, "sso_password_login": False})
    client = TestClient(create_app(settings=locked, clock=clock, http_transport=httpx.MockTransport(idp.handler)))
    r = client.post("/auth/login", json={"email": "ucitel@skola.cz", "password": "heslo123"})
    assert r.status_code == 403
    assert client.get("/auth/sso/config").json()["password_login"] is False
