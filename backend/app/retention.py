"""Mazání dat po skončení akademického roku a výmaz auditních údajů (IP, otisky zařízení)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .models import Attendance, Excuse, LessonSession


def purge_before(db: Session, cutoff: datetime, settings: Settings) -> dict[str, int]:
    """Smaže hodiny začínající před `cutoff` včetně docházky, omluvenek a jejich příloh."""
    lessons = db.scalars(select(LessonSession).where(LessonSession.starts_at < cutoff)).all()
    lesson_ids = [l.id for l in lessons]
    counts = {"sessions": 0, "attendance": 0, "excuses": 0, "attachments": 0}
    if not lesson_ids:
        return counts

    for excuse in db.scalars(select(Excuse).where(Excuse.session_id.in_(lesson_ids))).all():
        if excuse.attachment_path:
            try:
                os.remove(os.path.join(settings.upload_dir, excuse.attachment_path))
                counts["attachments"] += 1
            except OSError:
                pass
        db.delete(excuse)
        counts["excuses"] += 1
    for record in db.scalars(select(Attendance).where(Attendance.session_id.in_(lesson_ids))).all():
        db.delete(record)
        counts["attendance"] += 1
    for lesson in lessons:
        db.delete(lesson)
        counts["sessions"] += 1
    db.commit()
    return counts


def scrub_audit(db: Session, older_than: datetime) -> int:
    """Vynuluje IP adresy a otisky zařízení u záznamů starších než `older_than`. Vrací počet záznamů."""
    records = db.scalars(
        select(Attendance)
        .join(LessonSession, LessonSession.id == Attendance.session_id)
        .where(LessonSession.starts_at < older_than, Attendance.ip.is_not(None) | Attendance.device_hash.is_not(None))
    ).all()
    for record in records:
        record.ip = None
        record.device_hash = None
    db.commit()
    return len(records)


def cutoff_for_days(now: datetime, days: int) -> datetime:
    return now - timedelta(days=days)
