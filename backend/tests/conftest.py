from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402

T0 = datetime(2026, 11, 2, 9, 0, 0)  # naivní UTC


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        from datetime import timedelta

        self.now = self.now + timedelta(**kwargs)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(T0)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", secret_key="test-secret")


@pytest.fixture
def app(settings, clock):
    return create_app(settings=settings, clock=clock)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def db(app):
    session: Session = app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def make_user(app, email: str, name: str, role: str, password: str | None = "heslo123") -> User:
    factory = app.state.session_factory
    with factory() as s:
        user = User(
            email=email,
            name=name,
            role=role,
            password_hash=hash_password(password) if password else None,
        )
        s.add(user)
        s.commit()
        s.refresh(user)
        return user


def login(client, email: str, password: str = "heslo123") -> dict:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


DEVICE_A = "device-aaaaaaaa-1111"
DEVICE_B = "device-bbbbbbbb-2222"
