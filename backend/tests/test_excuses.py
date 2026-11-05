from __future__ import annotations

from datetime import timedelta

import pytest

from conftest import DEVICE_A, T0, login, make_user
from test_api import checkin, classroom, qr, start  # noqa: F401  (fixtures + helpers)

PDF = ("priloha.pdf", b"%PDF-1.4 test", "application/pdf")


def submit(client, c, email, text="Lékařská prohlídka v tento den", file=PDF, lesson_id=None):
    lesson_id = lesson_id or c["lesson"]["id"]
    files = {"file": (file[0], file[1], file[2])} if file else None
    return client.post(
        f"/sessions/{lesson_id}/excuses",
        data={"text": text},
        files=files,
        headers=c["students"][email],
    )


def teacher_pending(client, c):
    return client.get("/excuses", headers=c["teacher"]).json()


def test_student_submits_excuse_with_attachment(client, classroom):
    r = submit(client, classroom, "bob@skola.cz")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["has_attachment"] is True
    assert body["attachment_name"] == "priloha.pdf"
    pending = teacher_pending(client, classroom)
    assert len(pending) == 1
    assert pending[0]["student"]["email"] == "bob@skola.cz"


def test_duplicate_excuse_is_rejected(client, classroom):
    assert submit(client, classroom, "bob@skola.cz").status_code == 201
    assert submit(client, classroom, "bob@skola.cz").status_code == 409


def test_excuse_rejects_wrong_file_type_and_size(client, classroom, settings):
    r = submit(client, classroom, "bob@skola.cz", file=("skript.exe", b"MZ", "application/x-msdownload"))
    assert r.status_code == 415
    big = b"0" * (settings.max_upload_bytes + 1)
    r = submit(client, classroom, "bob@skola.cz", file=("velky.pdf", big, "application/pdf"))
    assert r.status_code == 413


def test_student_outside_group_cannot_submit(app, client, classroom):
    make_user(app, "cizi@skola.cz", "Cizí", "student")
    c = dict(classroom, students={**classroom["students"], "cizi@skola.cz": login(client, "cizi@skola.cz")})
    assert submit(client, c, "cizi@skola.cz").status_code == 403


def test_present_student_cannot_submit_excuse(client, classroom):
    start(client, classroom)
    checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=qr(client, classroom))
    assert submit(client, classroom, "alice@skola.cz").status_code == 409


def test_approved_excuse_marks_excused_and_is_not_an_absence(client, classroom, clock):
    submit(client, classroom, "bob@skola.cz")
    excuse_id = teacher_pending(client, classroom)[0]["id"]
    r = client.post(f"/excuses/{excuse_id}/decision", json={"decision": "approve", "note": "OK"},
                    headers=classroom["teacher"])
    assert r.status_code == 200 and r.json()["status"] == "approved"

    clock.advance(hours=1, minutes=1)  # hodina skončí → Bob bude omluven, ne nepřítomen
    bob = client.get("/me/attendance", headers=classroom["students"]["bob@skola.cz"]).json()
    assert bob["absences"] == 0
    assert bob["items"][0]["status"] == "excused"
    live = client.get(f"/sessions/{classroom['lesson']['id']}/attendance", headers=classroom["teacher"]).json()
    assert {s["email"]: s["status"] for s in live["students"]}["bob@skola.cz"] == "excused"


def test_approval_during_running_session_applies_at_close(client, classroom, clock):
    start(client, classroom)
    submit(client, classroom, "bob@skola.cz")
    excuse_id = teacher_pending(client, classroom)[0]["id"]
    client.post(f"/excuses/{excuse_id}/decision", json={"decision": "approve"}, headers=classroom["teacher"])
    clock.advance(hours=1, minutes=1)
    bob = client.get("/me/attendance", headers=classroom["students"]["bob@skola.cz"]).json()
    assert bob["items"][0]["status"] == "excused"


def test_rejected_excuse_keeps_absence_and_can_be_resubmitted(client, classroom, clock):
    submit(client, classroom, "bob@skola.cz")
    excuse_id = teacher_pending(client, classroom)[0]["id"]
    client.post(f"/excuses/{excuse_id}/decision", json={"decision": "reject", "note": "Chybí doklad"},
                headers=classroom["teacher"])
    clock.advance(hours=1, minutes=1)
    bob = client.get("/me/attendance", headers=classroom["students"]["bob@skola.cz"]).json()
    assert bob["absences"] == 1

    mine = client.get("/me/excuses", headers=classroom["students"]["bob@skola.cz"]).json()
    assert mine[0]["status"] == "rejected" and mine[0]["decision_note"] == "Chybí doklad"
    # znovu odeslat po zamítnutí jde
    assert submit(client, classroom, "bob@skola.cz", text="Přikládám potvrzení od lékaře").status_code == 201


def test_decision_is_final(client, classroom):
    submit(client, classroom, "bob@skola.cz")
    excuse_id = teacher_pending(client, classroom)[0]["id"]
    client.post(f"/excuses/{excuse_id}/decision", json={"decision": "approve"}, headers=classroom["teacher"])
    r = client.post(f"/excuses/{excuse_id}/decision", json={"decision": "reject"}, headers=classroom["teacher"])
    assert r.status_code == 409


def test_other_teacher_cannot_decide_or_see_excuse(app, client, classroom):
    submit(client, classroom, "bob@skola.cz")
    excuse_id = teacher_pending(client, classroom)[0]["id"]
    make_user(app, "jiny@skola.cz", "Jiný", "teacher")
    other = login(client, "jiny@skola.cz")
    assert client.get("/excuses", headers=other).json() == []
    assert client.post(f"/excuses/{excuse_id}/decision", json={"decision": "approve"}, headers=other).status_code == 403
    assert client.get(f"/excuses/{excuse_id}/attachment", headers=other).status_code == 403


def test_attachment_visible_to_owner_and_teacher_only(app, client, classroom):
    submit(client, classroom, "bob@skola.cz")
    excuse_id = teacher_pending(client, classroom)[0]["id"]
    owner = client.get(f"/excuses/{excuse_id}/attachment", headers=classroom["students"]["bob@skola.cz"])
    assert owner.status_code == 200 and owner.content == PDF[1]
    teacher = client.get(f"/excuses/{excuse_id}/attachment", headers=classroom["teacher"])
    assert teacher.status_code == 200
    alice = client.get(f"/excuses/{excuse_id}/attachment", headers=classroom["students"]["alice@skola.cz"])
    assert alice.status_code == 403


def test_notifications_warn_near_absence_limit(client, classroom, clock):
    start(client, classroom)
    checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=qr(client, classroom))
    clock.advance(hours=1, minutes=1)  # hodina skončila: Bob má 1 absenci, Alice nemá žádnou
    notes = client.get("/me/notifications", headers=classroom["students"]["bob@skola.cz"]).json()
    assert any(n["type"] == "absence_limit" and n["level"] == "warning" for n in notes)
    alice_notes = client.get("/me/notifications", headers=classroom["students"]["alice@skola.cz"]).json()
    assert not any(n["type"] == "absence_limit" for n in alice_notes)


def test_notifications_for_teacher_and_decision_for_student(client, classroom):
    submit(client, classroom, "bob@skola.cz")
    teacher_notes = client.get("/me/notifications", headers=classroom["teacher"]).json()
    assert any(n["type"] == "pending_excuses" and n["count"] == 1 for n in teacher_notes)

    excuse_id = teacher_pending(client, classroom)[0]["id"]
    client.post(f"/excuses/{excuse_id}/decision", json={"decision": "approve"}, headers=classroom["teacher"])
    bob_notes = client.get("/me/notifications", headers=classroom["students"]["bob@skola.cz"]).json()
    assert any(n["type"] == "excuse_decision" and n["excuse_id"] == excuse_id for n in bob_notes)
