from __future__ import annotations

from datetime import timedelta

import pytest

from conftest import DEVICE_A, DEVICE_B, T0, login, make_user

STUDENTS_CSV = "email,name\nalice@skola.cz,Alice\nbob@skola.cz,Bob\ncarol@skola.cz,Carol\n"


@pytest.fixture
def classroom(app, client, clock):
    """Učitel, tři studenti zapsaní do skupiny a jedna připravená hodina (09:00–10:00 UTC)."""
    make_user(app, "ucitel@skola.cz", "Jana Učitelová", "teacher")
    teacher = login(client, "ucitel@skola.cz")
    # Studenti mají účet s heslem dřív, než se importují do skupiny (import účty jen najde a zapíše).
    students = {}
    for email in ("alice@skola.cz", "bob@skola.cz", "carol@skola.cz"):
        make_user(app, email, email.split("@")[0].title(), "student")
        students[email] = login(client, email)
    course = client.post("/courses", json={"name": "ZPP", "semester": "LS2026"}, headers=teacher).json()
    group = client.post(f"/courses/{course['id']}/groups", json={"name": "Cvičení 1"}, headers=teacher).json()
    imported = client.post(
        f"/groups/{group['id']}/students/import",
        content=STUDENTS_CSV.encode(),
        headers={**teacher, "Content-Type": "text/csv"},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json() == {"created_users": 0, "enrolled": 3, "skipped_rows": 0}
    lesson = client.post(
        f"/groups/{group['id']}/sessions",
        json={"starts_at": T0.isoformat(), "ends_at": (T0 + timedelta(hours=1)).isoformat()},
        headers=teacher,
    ).json()
    return {"teacher": teacher, "group": group, "lesson": lesson, "students": students}


def start(client, c):
    r = client.post(f"/sessions/{c['lesson']['id']}/start", headers=c["teacher"])
    assert r.status_code == 200, r.text
    return r.json()


def qr(client, c) -> str:
    r = client.get(f"/sessions/{c['lesson']['id']}/qr", headers=c["teacher"])
    assert r.status_code == 200, r.text
    return r.json()["qr_token"]


def checkin(client, c, student_email, device, *, qr_token=None, code=None):
    body = {"session_id": c["lesson"]["id"], "device_id": device}
    if qr_token is not None:
        body["qr_token"] = qr_token
    if code is not None:
        body["code"] = code
    return client.post("/attendance/checkin", json=body, headers=c["students"][student_email])


# --- přihlášení a role -----------------------------------------------------

def test_login_rejects_wrong_password(app, client):
    make_user(app, "x@skola.cz", "X", "student")
    r = client.post("/auth/login", json={"email": "x@skola.cz", "password": "spatne"})
    assert r.status_code == 401


def test_me_returns_current_user(app, client):
    make_user(app, "ucitel@skola.cz", "Jana", "teacher")
    r = client.get("/auth/me", headers=login(client, "ucitel@skola.cz"))
    assert r.status_code == 200
    assert r.json()["role"] == "teacher"


def test_protected_endpoint_requires_token(client):
    assert client.get("/courses").status_code == 401


def test_student_cannot_create_course(app, client):
    make_user(app, "s@skola.cz", "S", "student")
    r = client.post("/courses", json={"name": "ZPP"}, headers=login(client, "s@skola.cz"))
    assert r.status_code == 403


def test_other_teacher_cannot_manage_group(app, client, classroom):
    make_user(app, "jiny@skola.cz", "Jiný", "teacher")
    other = login(client, "jiny@skola.cz")
    r = client.post(f"/groups/{classroom['group']['id']}/sessions",
                    json={"starts_at": T0.isoformat(), "ends_at": (T0 + timedelta(hours=1)).isoformat()},
                    headers=other)
    assert r.status_code == 403


# --- import a hodiny -------------------------------------------------------

def test_import_requires_email_column(app, client, classroom):
    r = client.post(f"/groups/{classroom['group']['id']}/students/import",
                    content=b"jmeno,mail\nA,a@b.cz\n",
                    headers={**classroom["teacher"], "Content-Type": "text/csv"})
    assert r.status_code == 400


def test_import_is_idempotent(client, classroom):
    r = client.post(f"/groups/{classroom['group']['id']}/students/import",
                    content=STUDENTS_CSV.encode(),
                    headers={**classroom["teacher"], "Content-Type": "text/csv"})
    assert r.json() == {"created_users": 0, "enrolled": 0, "skipped_rows": 0}


def test_session_end_must_be_after_start(client, classroom):
    r = client.post(f"/groups/{classroom['group']['id']}/sessions",
                    json={"starts_at": T0.isoformat(), "ends_at": T0.isoformat()},
                    headers=classroom["teacher"])
    assert r.status_code == 422


# --- check-in ---------------------------------------------------------------

def test_qr_checkin_marks_present(client, classroom):
    start(client, classroom)
    r = checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=qr(client, classroom))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "present"
    assert r.json()["method"] == "qr"


def test_checkin_is_idempotent_for_same_student(client, classroom):
    start(client, classroom)
    token = qr(client, classroom)
    first = checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=token)
    second = checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=token)
    assert first.status_code == second.status_code == 200
    assert first.json()["recorded_at"] == second.json()["recorded_at"]


def test_late_checkin_after_threshold(client, classroom, clock):
    start(client, classroom)
    clock.advance(minutes=11)
    r = checkin(client, classroom, "bob@skola.cz", DEVICE_B, qr_token=qr(client, classroom))
    assert r.json()["status"] == "late"


def test_expired_qr_token_is_rejected(client, classroom, clock):
    start(client, classroom)
    token = qr(client, classroom)
    clock.advance(seconds=60)  # o několik oken dál
    r = checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=token)
    assert r.status_code == 400


def test_forged_qr_token_is_rejected(client, classroom):
    start(client, classroom)
    token = qr(client, classroom)
    session_id, window, _ = token.split(".")
    forged = f"{session_id}.{window}.{'0' * 32}"
    r = checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=forged)
    assert r.status_code == 400


def test_numeric_code_checkin_and_expiry(client, classroom, clock):
    start(client, classroom)
    code_resp = client.get(f"/sessions/{classroom['lesson']['id']}/qr", headers=classroom["teacher"]).json()
    code = code_resp["code"]
    assert len(code) == 6
    assert checkin(client, classroom, "alice@skola.cz", DEVICE_A, code=code).status_code == 200

    clock.advance(seconds=61)
    r = checkin(client, classroom, "carol@skola.cz", "device-cccccccc-3333", code=code)
    assert r.status_code == 400


def test_same_device_cannot_check_in_two_students(client, classroom):
    start(client, classroom)
    token = qr(client, classroom)
    assert checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=token).status_code == 200
    r = checkin(client, classroom, "bob@skola.cz", DEVICE_A, qr_token=token)
    assert r.status_code == 409


def test_student_not_in_group_is_rejected(app, client, classroom):
    make_user(app, "cizi@skola.cz", "Cizí", "student")
    start(client, classroom)
    r = client.post(
        "/attendance/checkin",
        json={"session_id": classroom["lesson"]["id"], "device_id": DEVICE_A, "qr_token": qr(client, classroom)},
        headers=login(client, "cizi@skola.cz"),
    )
    assert r.status_code == 403


def test_checkin_rejected_before_session_started(client, classroom):
    r = checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token="1.1.x")
    assert r.status_code == 409


# --- ruční úpravy, živý přehled, uzavření ----------------------------------

def test_manual_override_and_live_view(client, classroom):
    start(client, classroom)
    alice_id = client.get("/auth/me", headers=classroom["students"]["alice@skola.cz"]).json()["id"]
    r = client.put(f"/sessions/{classroom['lesson']['id']}/attendance/{alice_id}",
                   json={"status": "excused"}, headers=classroom["teacher"])
    assert r.status_code == 200
    live = client.get(f"/sessions/{classroom['lesson']['id']}/attendance", headers=classroom["teacher"]).json()
    statuses = {s["email"]: s["status"] for s in live["students"]}
    assert statuses["alice@skola.cz"] == "excused"
    assert statuses["bob@skola.cz"] == "none"
    assert live["counts"]["none"] == 2


def test_closing_marks_missing_students_absent(client, classroom, clock):
    start(client, classroom)
    checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=qr(client, classroom))
    clock.advance(hours=1, minutes=1)  # po konci hodiny
    live = client.get(f"/sessions/{classroom['lesson']['id']}/attendance", headers=classroom["teacher"]).json()
    statuses = {s["email"]: s["status"] for s in live["students"]}
    assert live["session"]["status"] == "closed"
    assert statuses == {"alice@skola.cz": "present", "bob@skola.cz": "absent", "carol@skola.cz": "absent"}


def test_student_sees_own_attendance_and_absences(client, classroom, clock):
    start(client, classroom)
    checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=qr(client, classroom))
    clock.advance(hours=1, minutes=1)
    bob = client.get("/me/attendance", headers=classroom["students"]["bob@skola.cz"]).json()
    assert bob["absences"] == 1
    assert bob["remaining"] == 1
    assert bob["items"][0]["status"] == "absent"
    alice = client.get("/me/attendance", headers=classroom["students"]["alice@skola.cz"]).json()
    assert alice["absences"] == 0
    assert alice["items"][0]["status"] == "present"


def test_student_cannot_list_sessions_of_foreign_group(app, client, classroom):
    make_user(app, "cizi@skola.cz", "Cizí", "student")
    r = client.get(f"/groups/{classroom['group']['id']}/sessions", headers=login(client, "cizi@skola.cz"))
    assert r.status_code == 403


def test_checkin_after_end_is_rejected(client, classroom, clock):
    start(client, classroom)
    token = qr(client, classroom)
    clock.advance(hours=1)
    r = checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=token)
    assert r.status_code == 409


# --- export a statistiky ----------------------------------------------------

def test_export_csv_contains_row_per_student(client, classroom, clock):
    start(client, classroom)
    checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=qr(client, classroom))
    clock.advance(hours=1, minutes=1)
    r = client.get(f"/groups/{classroom['group']['id']}/export.csv", headers=classroom["teacher"])
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("email,name,2026-11-02 09:00")
    assert "alice@skola.cz,Alice,present" in lines[1]
    assert "bob@skola.cz,Bob,absent" in lines[2]


def test_stats_flags_students_over_absence_limit(client, classroom, clock):
    group_id = classroom["group"]["id"]
    teacher = classroom["teacher"]

    # Hodina z fixture: Alice přijde, Bob a Carol ne.
    start(client, classroom)
    checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=qr(client, classroom))
    lessons = [classroom["lesson"]]

    # Další tři hodiny: opět jen Alice → Bob a Carol mají 4 absence (limit je 2).
    for i in range(1, 4):
        begin = T0 + timedelta(days=i)
        clock.now = begin
        teacher = login(client, "ucitel@skola.cz")  # token je platný 12 h, po posunu času obnovit
        alice = login(client, "alice@skola.cz")
        lesson = client.post(
            f"/groups/{group_id}/sessions",
            json={"starts_at": begin.isoformat(), "ends_at": (begin + timedelta(hours=1)).isoformat()},
            headers=teacher,
        ).json()
        lessons.append(lesson)
        client.post(f"/sessions/{lesson['id']}/start", headers=teacher)
        token = client.get(f"/sessions/{lesson['id']}/qr", headers=teacher).json()["qr_token"]
        r = client.post("/attendance/checkin",
                        json={"session_id": lesson["id"], "device_id": DEVICE_A, "qr_token": token},
                        headers=alice)
        assert r.status_code == 200, r.text

    clock.now = T0 + timedelta(days=4)  # všechny hodiny už skončily → automaticky se uzavřou
    teacher = login(client, "ucitel@skola.cz")
    stats = client.get(f"/groups/{group_id}/stats", headers=teacher).json()
    by_email = {s["email"]: s for s in stats["students"]}
    assert stats["closed_sessions"] == 4
    assert by_email["bob@skola.cz"]["absent"] == 4
    assert by_email["bob@skola.cz"]["over_limit"] is True
    assert by_email["alice@skola.cz"]["over_limit"] is False
    assert by_email["alice@skola.cz"]["attendance_rate"] == 1.0
    assert by_email["bob@skola.cz"]["attendance_rate"] == 0.0
