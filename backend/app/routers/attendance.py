"""Docházka: spuštění hodiny, rotující QR kód, check-in studenta, ruční úpravy, export a statistiky."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Literal

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import ensure_can_manage_group, get_current_user, get_db, get_now, get_settings, require_teacher
from ..models import Attendance, Enrollment, Group, LessonSession, User
from ..security import read_auth_token
from ..security import (
    check_qr_token,
    current_window,
    hash_device,
    make_qr_token,
    new_numeric_code,
    qr_seconds_left,
    to_epoch,
)
from ..services import close_lesson, distance_m, finalize_if_expired, live_snapshot, serialize_attendance, serialize_lesson
from .academics import get_lesson_or_404

router = APIRouter(tags=["attendance"])


class CheckinIn(BaseModel):
    session_id: int
    qr_token: str | None = None
    code: str | None = Field(default=None, min_length=6, max_length=6)
    device_id: str = Field(min_length=8, max_length=200)
    # Poloha se použije jen k jednorázovému ověření a neukládá se.
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=100000)


class ManualIn(BaseModel):
    status: Literal["present", "late", "absent", "excused"]


def _lesson_for_teacher(db: Session, session_id: int, teacher: User) -> tuple[LessonSession, Group]:
    lesson = get_lesson_or_404(db, session_id)
    group = db.get(Group, lesson.group_id)
    ensure_can_manage_group(teacher, group)
    return lesson, group


MAX_ACCURACY_M = 100  # horší přesnost GPS nelze spolehlivě vyhodnotit


def _verify_location(db: Session, lesson: LessonSession, body: "CheckinIn", settings: Settings) -> bool | None:
    """Vrací None, pokud geofence u skupiny není; jinak True, nebo vyvolá chybu mimo učebnu."""
    group = db.get(Group, lesson.group_id)
    if group.latitude is None or group.longitude is None or group.geofence_radius_m is None:
        return None
    if body.latitude is None or body.longitude is None:
        raise HTTPException(status_code=400, detail="Pro zápis je potřeba povolit sdílení polohy")
    if body.accuracy_m is not None and body.accuracy_m > MAX_ACCURACY_M:
        raise HTTPException(status_code=400, detail="Poloha je příliš nepřesná, zkuste to znovu na otevřeném místě")
    distance = distance_m(group.latitude, group.longitude, body.latitude, body.longitude)
    if distance > group.geofence_radius_m:
        raise HTTPException(status_code=403, detail="Nejste v učebně, docházku nelze zapsat")
    return True


def _is_enrolled(db: Session, user_id: int, group_id: int) -> bool:
    return db.get(Enrollment, (user_id, group_id)) is not None


@router.post("/sessions/{session_id}/start")
def start_session(
    session_id: int,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
    now: datetime = Depends(get_now),
) -> dict:
    lesson, _ = _lesson_for_teacher(db, session_id, teacher)
    finalize_if_expired(db, lesson, now)
    if lesson.status != "ready":
        raise HTTPException(status_code=409, detail="Docházku nelze spustit (stav: %s)" % lesson.status)
    lesson.status = "running"
    db.commit()
    return serialize_lesson(lesson)


@router.post("/sessions/{session_id}/close")
def close_session(
    session_id: int,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
    now: datetime = Depends(get_now),
) -> dict:
    lesson, _ = _lesson_for_teacher(db, session_id, teacher)
    if lesson.status != "closed":
        close_lesson(db, lesson, now)
    return serialize_lesson(lesson)


@router.get("/sessions/{session_id}/qr")
def current_qr(
    session_id: int,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
) -> dict:
    """Aktuální rotující QR token a číselný kód. Promítá se na obrazovku ve třídě."""
    lesson, _ = _lesson_for_teacher(db, session_id, teacher)
    finalize_if_expired(db, lesson, now)
    if lesson.status != "running":
        raise HTTPException(status_code=409, detail="Docházka není spuštěna")

    window = current_window(now, settings.qr_window_seconds)
    if lesson.code is None or lesson.code_expires_at is None or now >= lesson.code_expires_at:
        lesson.code = new_numeric_code()
        lesson.code_expires_at = now + timedelta(seconds=settings.code_ttl_seconds)
        db.commit()

    return {
        "qr_token": make_qr_token(settings.secret_key, lesson.id, window),
        "qr_expires_in": qr_seconds_left(now, settings.qr_window_seconds),
        "code": lesson.code,
        "code_expires_in": max(0, to_epoch(lesson.code_expires_at) - to_epoch(now)),
    }


@router.post("/attendance/checkin")
def checkin(
    body: CheckinIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
) -> dict:
    lesson = get_lesson_or_404(db, body.session_id)
    finalize_if_expired(db, lesson, now)
    if lesson.status != "running":
        raise HTTPException(status_code=409, detail="Docházka pro tuto hodinu není otevřena")

    if body.qr_token is not None:
        method = "qr"
        valid = check_qr_token(settings.secret_key, body.qr_token, lesson.id, now, settings.qr_window_seconds)
    elif body.code is not None:
        method = "code"
        valid = (
            lesson.code is not None
            and lesson.code_expires_at is not None
            and now < lesson.code_expires_at
            and body.code == lesson.code
        )
    else:
        raise HTTPException(status_code=422, detail="Chybí QR token nebo kód")
    if not valid:
        raise HTTPException(status_code=400, detail="Neplatný nebo prošlý kód")

    if not _is_enrolled(db, user.id, lesson.group_id):
        raise HTTPException(status_code=403, detail="Nejste zapsáni do této skupiny")

    existing = db.get(Attendance, (lesson.id, user.id))
    if existing is not None:
        return serialize_attendance(existing)

    device_hash = hash_device(settings.secret_key, body.device_id)
    clash = db.scalar(
        select(Attendance).where(
            Attendance.session_id == lesson.id,
            Attendance.device_hash == device_hash,
            Attendance.user_id != user.id,
        )
    )
    if clash is not None:
        raise HTTPException(status_code=409, detail="Z tohoto zařízení již proběhl zápis jiného studenta")

    geo_verified = _verify_location(db, lesson, body, settings)

    late = now > lesson.starts_at + timedelta(minutes=settings.late_minutes)
    record = Attendance(
        session_id=lesson.id,
        user_id=user.id,
        status="late" if late else "present",
        method=method,
        recorded_at=now,
        device_hash=device_hash,
        ip=request.client.host if request.client else None,
        geo_verified=geo_verified,
    )
    db.add(record)
    db.commit()
    return serialize_attendance(record)


@router.get("/me/attendance")
def my_attendance(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
) -> dict:
    """Vlastní docházka napříč skupinami: stav u každé hodiny a počet absencí."""
    group_rows = db.execute(
        select(Group).join(Enrollment, Enrollment.group_id == Group.id).where(Enrollment.user_id == user.id)
    ).scalars().all()
    items = []
    for group in group_rows:
        lessons = db.scalars(
            select(LessonSession).where(LessonSession.group_id == group.id).order_by(LessonSession.starts_at)
        ).all()
        for lesson in lessons:
            finalize_if_expired(db, lesson, now)
            record = db.get(Attendance, (lesson.id, user.id))
            items.append(
                {
                    "session_id": lesson.id,
                    "group_id": group.id,
                    "group_name": group.name,
                    "starts_at": lesson.starts_at.isoformat(),
                    "ends_at": lesson.ends_at.isoformat(),
                    "session_status": lesson.status,
                    "status": record.status if record else None,
                    "recorded_at": record.recorded_at.isoformat() if record else None,
                }
            )
    items.sort(key=lambda i: i["starts_at"])
    absences = sum(1 for i in items if i["status"] == "absent")
    return {
        "absences": absences,
        "absence_limit": settings.absence_limit,
        "remaining": max(0, settings.absence_limit - absences),
        "items": items,
    }


@router.put("/sessions/{session_id}/attendance/{user_id}")
def manual_attendance(
    session_id: int,
    user_id: int,
    body: ManualIn,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
    now: datetime = Depends(get_now),
) -> dict:
    """Ruční zápis nebo oprava vyučujícím (přítomen, nepřítomen, pozdě, omluven)."""
    lesson, _ = _lesson_for_teacher(db, session_id, teacher)
    if not _is_enrolled(db, user_id, lesson.group_id):
        raise HTTPException(status_code=404, detail="Student není zapsán do skupiny")
    record = db.get(Attendance, (lesson.id, user_id))
    if record is None:
        record = Attendance(session_id=lesson.id, user_id=user_id)
        db.add(record)
    record.status = body.status
    record.method = "manual"
    record.recorded_at = now
    db.commit()
    return serialize_attendance(record)


@router.get("/sessions/{session_id}/attendance")
def live_attendance(
    session_id: int,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
    now: datetime = Depends(get_now),
) -> dict:
    """Živý přehled hodiny (REST varianta; WebSocket viz níže)."""
    lesson, _ = _lesson_for_teacher(db, session_id, teacher)
    return live_snapshot(db, lesson, now)


LIVE_POLL_SECONDS = 1.0
AUTH_TIMEOUT_SECONDS = 5.0


@router.websocket("/ws/sessions/{session_id}/attendance")
async def live_attendance_ws(websocket: WebSocket, session_id: int) -> None:
    """Push živého přehledu. Token se posílá jako první zpráva ({"token": "..."}), ne v URL.

    Server každou sekundu porovná stav s DB a pošle ho jen při změně.
    """
    app = websocket.app
    settings: Settings = app.state.settings

    def authorize(token: str) -> bool:
        payload = read_auth_token(settings.secret_key, token, app.state.clock())
        if payload is None:
            return False
        with app.state.session_factory() as db:
            user = db.get(User, payload["uid"])
            if user is None or user.role not in ("teacher", "admin"):
                return False
            lesson = db.get(LessonSession, session_id)
            if lesson is None:
                return False
            group = db.get(Group, lesson.group_id)
            return user.role == "admin" or group.teacher_id == user.id

    def snapshot() -> dict | None:
        with app.state.session_factory() as db:
            lesson = db.get(LessonSession, session_id)
            if lesson is None:
                return None
            return live_snapshot(db, lesson, app.state.clock())

    await websocket.accept()
    try:
        message = await asyncio.wait_for(websocket.receive_json(), AUTH_TIMEOUT_SECONDS)
        token = message.get("token") if isinstance(message, dict) else None
        if not isinstance(token, str) or not await asyncio.to_thread(authorize, token):
            await websocket.send_json({"error": "Neplatné přihlášení nebo chybí oprávnění"})
            await websocket.close(code=1008)
            return

        last = None
        while True:
            current = await asyncio.to_thread(snapshot)
            if current is None:
                await websocket.close(code=1008)
                return
            if current != last:
                await websocket.send_json(current)
                last = current
            try:
                # Přijatou zprávu od klienta nic neřeší (slouží k udržení spojení); důležité je odpojení.
                await asyncio.wait_for(websocket.receive_text(), LIVE_POLL_SECONDS)
            except asyncio.TimeoutError:
                pass
    except (WebSocketDisconnect, asyncio.TimeoutError):
        return


@router.get("/groups/{group_id}/export.csv")
def export_group(
    group_id: int,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
    now: datetime = Depends(get_now),
) -> Response:
    """Export docházky skupiny: řádek na studenta, sloupec na hodinu."""
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Skupina neexistuje")
    ensure_can_manage_group(teacher, group)

    lessons = db.scalars(
        select(LessonSession).where(LessonSession.group_id == group.id).order_by(LessonSession.starts_at)
    ).all()
    for lesson in lessons:
        finalize_if_expired(db, lesson, now)

    students = db.execute(
        select(User)
        .join(Enrollment, Enrollment.user_id == User.id)
        .where(Enrollment.group_id == group.id)
        .order_by(User.name, User.email)
    ).scalars().all()
    records = {
        (r.session_id, r.user_id): r.status
        for r in db.scalars(
            select(Attendance).join(LessonSession, LessonSession.id == Attendance.session_id)
            .where(LessonSession.group_id == group.id)
        ).all()
    }

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["email", "name"] + [l.starts_at.strftime("%Y-%m-%d %H:%M") for l in lessons])
    for student in students:
        row = [student.email, student.name]
        for lesson in lessons:
            row.append(records.get((lesson.id, student.id), "" if lesson.status == "running" else "absent"))
        writer.writerow(row)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="group-{group.id}-attendance.csv"'},
    )


@router.get("/groups/{group_id}/stats")
def group_stats(
    group_id: int,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
) -> dict:
    """Účast po studentech i po hodinách; upozornění na překročení limitu absencí."""
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Skupina neexistuje")
    ensure_can_manage_group(teacher, group)

    lessons = db.scalars(
        select(LessonSession).where(LessonSession.group_id == group.id).order_by(LessonSession.starts_at)
    ).all()
    closed = []
    for lesson in lessons:
        finalize_if_expired(db, lesson, now)
        if lesson.status == "closed":
            closed.append(lesson)
    closed_ids = {l.id for l in closed}

    records = [
        r for r in db.scalars(select(Attendance).where(Attendance.session_id.in_(closed_ids))).all()
    ] if closed_ids else []
    by_student: dict[int, dict[str, int]] = {}
    by_session: dict[int, dict[str, int]] = {l.id: {"present": 0, "late": 0, "total": 0} for l in closed}
    for r in records:
        by_student.setdefault(r.user_id, {"present": 0, "late": 0, "absent": 0, "excused": 0})
        by_student[r.user_id][r.status] += 1
        if r.status in ("present", "late"):
            by_session[r.session_id][r.status] += 1
        by_session[r.session_id]["total"] += 1

    students = db.execute(
        select(User).join(Enrollment, Enrollment.user_id == User.id).where(Enrollment.group_id == group.id)
        .order_by(User.name, User.email)
    ).scalars().all()
    student_rows = []
    for s in students:
        c = by_student.get(s.id, {"present": 0, "late": 0, "absent": 0, "excused": 0})
        recorded_present = c["present"] + c["late"]
        student_rows.append(
            {
                "user_id": s.id,
                "name": s.name,
                "email": s.email,
                "present": c["present"],
                "late": c["late"],
                "excused": c["excused"],
                "absent": c["absent"],
                "attendance_rate": round(recorded_present / len(closed), 3) if closed else None,
                "over_limit": c["absent"] > settings.absence_limit,
            }
        )

    return {
        "closed_sessions": len(closed),
        "absence_limit": settings.absence_limit,
        "students": student_rows,
        "sessions": [
            {
                "session_id": l.id,
                "starts_at": l.starts_at.isoformat(),
                "present": by_session[l.id]["present"] + by_session[l.id]["late"],
                "enrolled": len(students),
            }
            for l in closed
        ],
    }
