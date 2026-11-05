from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import httpx
from fastapi import FastAPI

from .config import Settings, check_production_settings, load_settings
from .db import Base, make_session_factory
from .push import default_sender
from .routers import academics, attendance, auth, excuses, push, sso
from .services import utcnow


def create_app(
    settings: Settings | None = None,
    clock: Callable[[], datetime] | None = None,
    http_transport: httpx.BaseTransport | None = None,
) -> FastAPI:
    """Továrna aplikace. Nastavení a hodiny lze podstrčit (testy, různá prostředí)."""
    settings = settings or load_settings()
    check_production_settings(settings)
    engine, session_factory = make_session_factory(settings.database_url)
    Base.metadata.create_all(engine)

    app = FastAPI(title="CheckIn API", version="0.1.0")
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.clock = clock or utcnow
    app.state.push_sender = default_sender  # testy mohou podstrčit vlastní odesílač
    app.state.http_transport = http_transport  # None = skutečná síť; testy podstrčí falešného IdP

    app.include_router(auth.router)
    app.include_router(academics.router)
    app.include_router(attendance.router)
    app.include_router(excuses.router)
    app.include_router(sso.router)
    app.include_router(push.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    return app
