"""Obchodní logika docházky: uzavírání hodin, serializace, pomocné převody času."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Attendance, Enrollment, Excuse, LessonSession


def utcnow() -> datetime:
    """Aktuální čas jako naivní UTC (SQLite ukládá datetime bez zóny)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def enrolled_user_ids(db: Session, group_id: int) -> list[int]:
    return list(db.scalars(select(Enrollment.user_id).where(Enrollment.group_id == group_id)).all())


def approved_excuse_user_ids(db: Session, session_id: int) -> set[int]:
    return set(
        db.scalars(
            select(Excuse.user_id).where(Excuse.session_id == session_id, Excuse.status == "approved")
        ).all()
    )


def close_lesson(db: Session, lesson: LessonSession, now: datetime) -> None:
    """Uzavře hodinu. Studentům bez záznamu zapíše nepřítomnost (automaticky)."""
    recorded = set(db.scalars(select(Attendance.user_id).where(Attendance.session_id == lesson.id)).all())
    excused = approved_excuse_user_ids(db, lesson.id)
    for user_id in enrolled_user_ids(db, lesson.group_id):
        if user_id not in recorded:
            db.add(
                Attendance(
                    session_id=lesson.id,
                    user_id=user_id,
                    status="excused" if user_id in excused else "absent",
                    method="excuse" if user_id in excused else "auto",
                    recorded_at=now,
                )
            )
    lesson.status = "closed"
    lesson.code = None
    lesson.code_expires_at = None
    db.commit()


def finalize_if_expired(db: Session, lesson: LessonSession, now: datetime) -> None:
    """Automatické uzavření docházky po konci hodiny (volá se při každém přístupu k hodině)."""
    if lesson.status != "closed" and now >= lesson.ends_at:
        close_lesson(db, lesson, now)


def serialize_lesson(lesson: LessonSession) -> dict:
    return {
        "id": lesson.id,
        "group_id": lesson.group_id,
        "starts_at": lesson.starts_at.isoformat(),
        "ends_at": lesson.ends_at.isoformat(),
        "status": lesson.status,
    }


def serialize_attendance(record: Attendance) -> dict:
    return {
        "session_id": record.session_id,
        "user_id": record.user_id,
        "status": record.status,
        "method": record.method,
        "recorded_at": record.recorded_at.isoformat(),
    }


def absence_counts(db: Session, group_id: int) -> dict[int, int]:
    """Počet neomluvených absencí studenta ve skupině (jen uzavřené hodiny)."""
    rows = db.execute(
        select(Attendance.user_id, func.count())
        .join(LessonSession, LessonSession.id == Attendance.session_id)
        .where(
            LessonSession.group_id == group_id,
            LessonSession.status == "closed",
            Attendance.status == "absent",
        )
        .group_by(Attendance.user_id)
    ).all()
    return {user_id: count for user_id, count in rows}


EARTH_RADIUS_M = 6_371_000


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Vzdálenost dvou bodů na zemi v metrech (haversinův vzorec)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))
