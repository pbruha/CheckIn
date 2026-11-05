from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import FastAPI

from .config import Settings, load_settings
from .db import Base, make_session_factory
from .routers import academics, attendance, auth, excuses
from .services import utcnow


def create_app(settings: Settings | None = None, clock: Callable[[], datetime] | None = None) -> FastAPI:
    """Továrna aplikace. Nastavení a hodiny lze podstrčit (testy, různá prostředí)."""
    settings = settings or load_settings()
    engine, session_factory = make_session_factory(settings.database_url)
    Base.metadata.create_all(engine)

    app = FastAPI(title="CheckIn API", version="0.1.0")
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.clock = clock or utcnow

    app.include_router(auth.router)
    app.include_router(academics.router)
    app.include_router(attendance.router)
    app.include_router(excuses.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    return app
