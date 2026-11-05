from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from py_vapid import Vapid01
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import PushSubscription
from conftest import login, make_user

ENDPOINT_A = "https://push.example.test/send/alice-phone"
ENDPOINT_T = "https://push.example.test/send/teacher-laptop"


class Recorder:
    def __init__(self):
        self.calls: list[tuple[dict, str]] = []
        self.gone: set[str] = set()

    def __call__(self, info: dict, data: str, settings: Settings) -> None:
        self.calls.append((info, data))
        if info["endpoint"] in self.gone:
            class Resp:
                status_code = 410
            exc = Exception("gone")
            exc.response = Resp()
            raise exc


@pytest.fixture
def push_env(tmp_path, clock):
    vapid = Vapid01()
    vapid.generate_keys()
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'push.db'}",
        secret_key="test-secret",
        vapid_private_key=vapid.private_pem().decode(),
        vapid_public_key="BPublicKeyForTests",
        upload_dir=str(tmp_path / "uploads"),
    )
    app = create_app(settings=settings, clock=clock)
    recorder = Recorder()
    app.state.push_sender = recorder
    client = TestClient(app)
    make_user(app, "ucitel@skola.cz", "Jana", "teacher")
    teacher = login(client, "ucitel@skola.cz")
    make_user(app, "alice@skola.cz", "Alice", "student")
    alice = login(client, "alice@skola.cz")
    course = client.post("/courses", json={"name": "ZPP"}, headers=teacher).json()
    group = client.post(f"/courses/{course['id']}/groups", json={"name": "Cvičení"}, headers=teacher).json()
    client.post(f"/groups/{group['id']}/students/import", content=b"email,name\nalice@skola.cz,Alice",
                headers={**teacher, "Content-Type": "text/csv"})
    lesson = client.post(f"/groups/{group['id']}/sessions",
                         json={"starts_at": "2026-11-02T09:00:00", "ends_at": "2026-11-02T10:00:00"},
                         headers=teacher).json()
    return {"app": app, "client": client, "teacher": teacher, "alice": alice, "lesson": lesson,
            "recorder": recorder, "settings": settings}


def subscribe(client, headers, endpoint):
    return client.post("/me/push-subscriptions", headers=headers,
                       json={"endpoint": endpoint, "keys": {"p256dh": "p256", "auth": "auth1"}})


def test_public_key_available_only_when_configured(client, push_env):
    assert push_env["client"].get("/push/public-key").json() == {"public_key": "BPublicKeyForTests"}
    assert client.get("/push/public-key").json() == {"public_key": None}  # bez VAPID konfigurace


def test_subscription_requires_https_endpoint(push_env):
    r = subscribe(push_env["client"], push_env["alice"], "http://insecure.example/x")
    assert r.status_code == 422


def test_student_excuse_decision_notifies_student(push_env):
    c = push_env["client"]
    subscribe(c, push_env["alice"], ENDPOINT_A)
    r = c.post(f"/sessions/{push_env['lesson']['id']}/excuses", data={"text": "Lékař"},
               headers=push_env["alice"])
    assert r.status_code == 201
    excuse_id = r.json()["id"]
    c.post(f"/excuses/{excuse_id}/decision", json={"decision": "approve", "note": "OK"},
           headers=push_env["teacher"])
    info, data = push_env["recorder"].calls[-1]
    payload = json.loads(data)
    assert info["endpoint"] == ENDPOINT_A
    assert payload["title"] == "Omluvenka schválena" and payload["url"] == "/student/excuses"


def test_new_excuse_notifies_teacher(push_env):
    c = push_env["client"]
    subscribe(c, push_env["teacher"], ENDPOINT_T)
    c.post(f"/sessions/{push_env['lesson']['id']}/excuses", data={"text": "Lékař"}, headers=push_env["alice"])
    info, data = push_env["recorder"].calls[-1]
    assert info["endpoint"] == ENDPOINT_T
    assert json.loads(data)["title"] == "Nová omluvenka"


def test_gone_subscription_is_removed(push_env):
    c = push_env["client"]
    subscribe(c, push_env["alice"], ENDPOINT_A)
    push_env["recorder"].gone.add(ENDPOINT_A)
    c.post(f"/sessions/{push_env['lesson']['id']}/excuses", data={"text": "Lékař"}, headers=push_env["alice"])
    c.post("/excuses/1/decision", json={"decision": "reject"}, headers=push_env["teacher"])
    with push_env["app"].state.session_factory() as db:
        assert db.scalars(select(PushSubscription)).all() == []


def test_unsubscribe_removes_endpoint(push_env):
    c = push_env["client"]
    subscribe(c, push_env["alice"], ENDPOINT_A)
    r = c.request("DELETE", "/me/push-subscriptions", json={"endpoint": ENDPOINT_A}, headers=push_env["alice"])
    assert r.json() == {"subscribed": False}
    with push_env["app"].state.session_factory() as db:
        assert db.scalars(select(PushSubscription)).all() == []

