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
    )
