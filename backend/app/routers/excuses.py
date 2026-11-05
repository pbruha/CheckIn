"""Omluvenky: odeslání studentem (text + příloha), schvalování vyučujícím, přílohy a notifikace."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import ensure_can_manage_group, get_current_user, get_db, get_now, get_settings, require_teacher
from ..models import Attendance, Enrollment, Excuse, Group, LessonSession, User
from ..push import notify_users
from ..services import absence_counts, finalize_if_expired, serialize_lesson
from .academics import get_lesson_or_404

router = APIRouter(tags=["excuses"])

ALLOWED_TYPES = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=500)


def serialize_excuse(ex: Excuse) -> dict:
    return {
        "id": ex.id,
        "session_id": ex.session_id,
        "status": ex.status,
        "text": ex.text,
        "has_attachment": ex.attachment_path is not None,
        "attachment_name": ex.attachment_name,
        "created_at": ex.created_at.isoformat(),
        "decided_at": ex.decided_at.isoformat() if ex.decided_at else None,
        "decision_note": ex.decision_note,
    }


def _store_attachment(settings: Settings, upload: UploadFile, data: bytes) -> tuple[str, str, str]:
    os.makedirs(settings.upload_dir, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ALLOWED_TYPES[upload.content_type]}"
    with open(os.path.join(settings.upload_dir, stored), "wb") as fh:
        fh.write(data)
    name = os.path.basename(upload.filename or "priloha")[:255]
    return stored, name, upload.content_type


def _remove_attachment(settings: Settings, stored: str | None) -> None:
    if stored:
        try:
            os.remove(os.path.join(settings.upload_dir, stored))
        except OSError:
            pass


def _load_excuse_for_manager(db: Session, excuse_id: int, user: User) -> tuple[Excuse, Group]:
    excuse = db.get(Excuse, excuse_id)
    if excuse is None:
        raise HTTPException(status_code=404, detail="Omluvenka neexistuje")
    lesson = db.get(LessonSession, excuse.session_id)
    group = db.get(Group, lesson.group_id)
    ensure_can_manage_group(user, group)
    return excuse, group


@router.post("/sessions/{session_id}/excuses", status_code=201)
async def submit_excuse(
    session_id: int,
    request: Request,
    background: BackgroundTasks,
    text: str = Form(min_length=3, max_length=2000),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
) -> dict:
    lesson = get_lesson_or_404(db, session_id)
    if db.get(Enrollment, (user.id, lesson.group_id)) is None:
        raise HTTPException(status_code=403, detail="Nejste zapsáni do této skupiny")
    record = db.get(Attendance, (lesson.id, user.id))
    if record is not None and record.status in ("present", "late"):
        raise HTTPException(status_code=409, detail="Na hodině jste byli zapsáni jako přítomni")

    attachment: tuple[str, str, str] | None = None
    if file is not None and file.filename:
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=415, detail="Příloha musí být PDF, PNG nebo JPG")
        data = await file.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Příloha je větší než povolených 5 MB")
        attachment = _store_attachment(settings, file, data)

    existing = db.scalar(select(Excuse).where(Excuse.user_id == user.id, Excuse.session_id == lesson.id))
    if existing is not None:
        if existing.status != "rejected":
            if attachment:
                _remove_attachment(settings, attachment[0])
            raise HTTPException(status_code=409, detail="Omluvenka k této hodině už existuje")
        # Zamítnutou omluvenku lze znovu odeslat – nahradí se obsah.
        _remove_attachment(settings, existing.attachment_path)
        excuse = existing
        excuse.status = "pending"
        excuse.created_at = now
        excuse.decided_at = None
        excuse.decided_by = None
        excuse.decision_note = None
    else:
        excuse = Excuse(user_id=user.id, session_id=lesson.id, status="pending", created_at=now)
        db.add(excuse)

    excuse.text = text.strip()
    if attachment:
        excuse.attachment_path, excuse.attachment_name, excuse.attachment_type = attachment
    else:
        excuse.attachment_path = excuse.attachment_name = excuse.attachment_type = None
    db.commit()
    group = db.get(Group, lesson.group_id)
    background.add_task(
        notify_users, request.app.state.session_factory, settings, request.app.state.push_sender,
        [group.teacher_id], "Nová omluvenka", f"{user.name or user.email} – {group.name}", "/teacher/excuses",
    )
    return serialize_excuse(excuse)


@router.get("/me/excuses")
def my_excuses(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    excuses = db.scalars(select(Excuse).where(Excuse.user_id == user.id).order_by(Excuse.created_at.desc())).all()
    return [serialize_excuse(e) for e in excuses]


@router.get("/excuses")
def manage_excuses(
    status: str = "pending",
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> list[dict]:
    """Omluvenky k hodinám skupin, které uživatel vyučuje (administrátor vidí všechny)."""
    query = (
        select(Excuse, User, LessonSession, Group)
        .join(User, User.id == Excuse.user_id)
        .join(LessonSession, LessonSession.id == Excuse.session_id)
        .join(Group, Group.id == LessonSession.group_id)
        .where(Excuse.status == status)
        .order_by(LessonSession.starts_at)
    )
    if teacher.role != "admin":
        query = query.where(Group.teacher_id == teacher.id)
    result = []
    for excuse, student, lesson, group in db.execute(query).all():
        item = serialize_excuse(excuse)
        item.update(
            {
                "student": {"id": student.id, "name": student.name, "email": student.email},
                "session": serialize_lesson(lesson),
                "group": {"id": group.id, "name": group.name},
            }
        )
        result.append(item)
    return result


@router.get("/excuses/{excuse_id}/attachment")
def download_attachment(
    excuse_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    excuse = db.get(Excuse, excuse_id)
    if excuse is None or excuse.attachment_path is None:
        raise HTTPException(status_code=404, detail="Příloha neexistuje")
    if excuse.user_id != user.id:
        lesson = db.get(LessonSession, excuse.session_id)
        ensure_can_manage_group(user, db.get(Group, lesson.group_id))
    return FileResponse(
        os.path.join(settings.upload_dir, excuse.attachment_path),
        media_type=excuse.attachment_type or "application/octet-stream",
        filename=excuse.attachment_name or "priloha",
    )


@router.post("/excuses/{excuse_id}/decision")
def decide_excuse(
    excuse_id: int,
    body: DecisionIn,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
) -> dict:
    excuse, _ = _load_excuse_for_manager(db, excuse_id, teacher)
    if excuse.status != "pending":
        raise HTTPException(status_code=409, detail="Omluvenka už byla vyřízena")
    lesson = db.get(LessonSession, excuse.session_id)
    record = db.get(Attendance, (lesson.id, excuse.user_id))

    if body.decision == "approve":
        excuse.status = "approved"
        # Hodina už skončila, nebo student zatím zapsaný není: stav „omluven“ se nastaví.
        # Běžící hodina se doplní při uzavření (viz close_lesson).
        if record is not None and record.status == "absent":
            record.status, record.method, record.recorded_at = "excused", "excuse", now
        elif record is None and lesson.status == "closed":
            db.add(
                Attendance(
                    session_id=lesson.id,
                    user_id=excuse.user_id,
                    status="excused",
                    method="excuse",
                    recorded_at=now,
                )
            )
    else:
        excuse.status = "rejected"
        if record is not None and record.method == "excuse":
            record.status, record.method, record.recorded_at = "absent", "auto", now

    excuse.decided_at = now
    excuse.decided_by = teacher.id
    excuse.decision_note = body.note
    db.commit()
    verdict = "schválena" if excuse.status == "approved" else "zamítnuta"
    background.add_task(
        notify_users, request.app.state.session_factory, settings, request.app.state.push_sender,
        [excuse.user_id], f"Omluvenka {verdict}", body.note or "Otevřete aplikaci pro detail", "/student/excuses",
    )
    return serialize_excuse(excuse)


@router.get("/me/notifications")
def my_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
) -> list[dict]:
    """Upozornění pro přehled: blížící se limit absencí, rozhodnutí o omluvenkách, čekající omluvenky."""
    items: list[dict] = []
    if user.role == "student":
        groups = db.scalars(
            select(Group).join(Enrollment, Enrollment.group_id == Group.id).where(Enrollment.user_id == user.id)
        ).all()
        for group in groups:
            # Nejdřív uzavřít hodiny, které už skončily, aby se započetla nepřítomnost.
            for lesson in db.scalars(select(LessonSession).where(LessonSession.group_id == group.id)).all():
                finalize_if_expired(db, lesson, now)
            absences = absence_counts(db, group.id).get(user.id, 0)
            remaining = settings.absence_limit - absences
            if remaining < 0:
                items.append({"type": "absence_limit", "level": "danger", "group": group.name,
                              "text": f"Překročili jste limit absencí ({absences} z {settings.absence_limit}).",
                              "absences": absences})
            elif remaining <= 1:
                items.append({"type": "absence_limit", "level": "warning", "group": group.name,
                              "text": f"Zbývá {remaining} povolená absence.", "absences": absences})

        recent = now - timedelta(days=14)
        decided = db.scalars(
            select(Excuse).where(Excuse.user_id == user.id, Excuse.decided_at.is_not(None),
                                 Excuse.decided_at >= recent).order_by(Excuse.decided_at.desc())
        ).all()
        for ex in decided:
            verdict = "schválena" if ex.status == "approved" else "zamítnuta"
            items.append({"type": "excuse_decision", "level": "info" if ex.status == "approved" else "warning",
                          "text": f"Vaše omluvenka byla {verdict}.", "excuse_id": ex.id,
                          "note": ex.decision_note})
    else:
        pending = db.scalars(
            select(Excuse).join(LessonSession, LessonSession.id == Excuse.session_id)
            .join(Group, Group.id == LessonSession.group_id)
            .where(Excuse.status == "pending",
                   *([] if user.role == "admin" else [Group.teacher_id == user.id]))
        ).all()
        if pending:
            items.append({"type": "pending_excuses", "level": "info", "count": len(pending),
                          "text": f"Čeká {len(pending)} omluvenek ke schválení."})
    return items
