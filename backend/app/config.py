from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./checkin.db"
    secret_key: str = "dev-secret-change-me"
    qr_window_seconds: int = 15  # QR kód se mění každých N sekund
    code_ttl_seconds: int = 60  # platnost číselného kódu
    late_minutes: int = 10  # hranice pro pozdní příchod
    absence_limit: int = 2  # povolený počet neomluvených absencí
    token_ttl_hours: int = 12
    upload_dir: str = "./uploads"
    max_upload_bytes: int = 5 * 1024 * 1024
    # SSO (OpenID Connect). Zapnuto, pokud je nastaven oidc_issuer.
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_uri: str | None = None  # musí být přesně registrovaná adresa callbacku
    oidc_scopes: str = "openid email profile"
    sso_allowed_domain: str | None = None  # např. skola.cz – omezí přihlášení na e-maily z domény
    sso_password_login: bool = True  # lze vypnout, pokud má být přihlašování jen školním účtem
    frontend_url: str = "http://localhost:5173"
    # Web Push (VAPID). Zapnuto, pokud je nastaven privátní klíč.
    vapid_private_key: str | None = None  # PEM, v env s \n jako řádkové zalomení
    vapid_public_key: str | None = None  # base64url, nepřímo se posílá prohlížeči
    vapid_subject: str = "mailto:checkin@example.org"


def load_settings() -> Settings:
    """Načte nastavení z proměnných prostředí (čte se při každém volání)."""
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./checkin.db"),
        secret_key=os.getenv("SECRET_KEY", "dev-secret-change-me"),
        qr_window_seconds=int(os.getenv("QR_WINDOW_SECONDS", "15")),
        code_ttl_seconds=int(os.getenv("CODE_TTL_SECONDS", "60")),
        late_minutes=int(os.getenv("LATE_MINUTES", "10")),
        absence_limit=int(os.getenv("ABSENCE_LIMIT", "2")),
        token_ttl_hours=int(os.getenv("TOKEN_TTL_HOURS", "12")),
        upload_dir=os.getenv("UPLOAD_DIR", "./uploads"),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024))),
        oidc_issuer=os.getenv("OIDC_ISSUER") or None,
        oidc_client_id=os.getenv("OIDC_CLIENT_ID") or None,
        oidc_client_secret=os.getenv("OIDC_CLIENT_SECRET") or None,
        oidc_redirect_uri=os.getenv("OIDC_REDIRECT_URI") or None,
        oidc_scopes=os.getenv("OIDC_SCOPES", "openid email profile"),
        sso_allowed_domain=(os.getenv("SSO_ALLOWED_DOMAIN") or "").lower() or None,
        sso_password_login=os.getenv("SSO_PASSWORD_LOGIN", "1") not in ("0", "false", "no"),
        frontend_url=os.getenv("FRONTEND_URL", "http://localhost:5173"),
        vapid_private_key=(os.getenv("VAPID_PRIVATE_KEY") or "").replace("\\n", "\n") or None,
        vapid_public_key=os.getenv("VAPID_PUBLIC_KEY") or None,
        vapid_subject=os.getenv("VAPID_SUBJECT", "mailto:checkin@example.org"),
    )
