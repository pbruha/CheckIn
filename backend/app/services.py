"""Obchodní logika docházky: uzavírání hodin, serializace, pomocné převody času."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Attendance, Enrollment, LessonSession


def utcnow() -> datetime:
    """Aktuální čas jako naivní UTC (SQLite ukládá datetime bez zóny)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def enrolled_user_ids(db: Session, group_id: int) -> list[int]:
    return list(db.scalars(select(Enrollment.user_id).where(Enrollment.group_id == group_id)).all())


def close_lesson(db: Session, lesson: LessonSession, now: datetime) -> None:
    """Uzavře hodinu. Studentům bez záznamu zapíše nepřítomnost (automaticky)."""
    recorded = set(db.scalars(select(Attendance.user_id).where(Attendance.session_id == lesson.id)).all())
    for user_id in enrolled_user_ids(db, lesson.group_id):
        if user_id not in recorded:
            db.add(
                Attendance(
                    session_id=lesson.id,
                    user_id=user_id,
                    status="absent",
                    method="auto",
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
