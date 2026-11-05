from __future__ import annotations

from conftest import DEVICE_A, login, make_user
from test_api import classroom, checkin, qr, start  # noqa: F401


def _ws_path(c):
    return f"/ws/sessions/{c['lesson']['id']}/attendance"


def test_teacher_receives_snapshot_and_live_updates(client, classroom):
    start(client, classroom)
    token = classroom["teacher"]["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(_ws_path(classroom)) as ws:
        ws.send_json({"token": token})
        first = ws.receive_json()
        assert first["counts"]["none"] == 3
        # změna z REST se objeví v push zprávě bez dotazování
        alice_id = client.get("/auth/me", headers=classroom["students"]["alice@skola.cz"]).json()["id"]
        r = client.put(f"/sessions/{classroom['lesson']['id']}/attendance/{alice_id}",
                       json={"status": "present"}, headers=classroom["teacher"])
        assert r.status_code == 200
        update = ws.receive_json()
        statuses = {s["email"]: s["status"] for s in update["students"]}
        assert statuses["alice@skola.cz"] == "present"


def test_checkin_is_pushed_to_teacher(client, classroom):
    start(client, classroom)
    token = classroom["teacher"]["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(_ws_path(classroom)) as ws:
        ws.send_json({"token": token})
        ws.receive_json()
        checkin(client, classroom, "bob@skola.cz", DEVICE_A, qr_token=qr(client, classroom))
        update = ws.receive_json()
        assert update["counts"]["present"] + update["counts"]["late"] == 1


def test_student_token_is_rejected(client, classroom):
    start(client, classroom)
    token = classroom["students"]["alice@skola.cz"]["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(_ws_path(classroom)) as ws:
        ws.send_json({"token": token})
        assert "error" in ws.receive_json()


def test_other_teacher_is_rejected(app, client, classroom):
    start(client, classroom)
    make_user(app, "jiny@skola.cz", "Jiný", "teacher")
    token = login(client, "jiny@skola.cz")["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(_ws_path(classroom)) as ws:
        ws.send_json({"token": token})
        assert "error" in ws.receive_json()


def test_missing_token_is_rejected(client, classroom):
    start(client, classroom)
    with client.websocket_connect(_ws_path(classroom)) as ws:
        ws.send_json({"nic": 1})
        assert "error" in ws.receive_json()
