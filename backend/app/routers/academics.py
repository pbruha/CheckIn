"""Předměty, skupiny, import studentů a hodiny (sessions)."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import ensure_can_manage_group, get_current_user, get_db, require_teacher
from ..models import Course, Enrollment, Group, LessonSession, User
from ..services import serialize_lesson, to_naive_utc

router = APIRouter(tags=["academics"])


class CourseIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    semester: str = Field(default="", max_length=50)


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class LocationIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: int = Field(ge=10, le=1000)


class SessionIn(BaseModel):
    starts_at: datetime
    ends_at: datetime


def _get_group(db: Session, group_id: int) -> Group:
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Skupina neexistuje")
    return group


@router.post("/courses", status_code=201)
def create_course(body: CourseIn, db: Session = Depends(get_db), _=Depends(require_teacher)) -> dict:
    course = Course(name=body.name, semester=body.semester)
    db.add(course)
    db.commit()
    return {"id": course.id, "name": course.name, "semester": course.semester}


@router.get("/courses")
def list_courses(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    courses = db.scalars(select(Course).order_by(Course.id)).all()
    return [{"id": c.id, "name": c.name, "semester": c.semester} for c in courses]


@router.post("/courses/{course_id}/groups", status_code=201)
def create_group(
    course_id: int,
    body: GroupIn,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> dict:
    if db.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="Předmět neexistuje")
    group = Group(course_id=course_id, name=body.name, teacher_id=teacher.id)
    db.add(group)
    db.commit()
    return {"id": group.id, "course_id": course_id, "name": group.name, "teacher_id": teacher.id}


def serialize_location(group: Group) -> dict:
    enabled = group.latitude is not None and group.longitude is not None and group.geofence_radius_m is not None
    return {
        "enabled": enabled,
        "latitude": group.latitude if enabled else None,
        "longitude": group.longitude if enabled else None,
        "radius_m": group.geofence_radius_m if enabled else None,
    }


@router.get("/groups/{group_id}/location")
def get_location(group_id: int, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> dict:
    group = _get_group(db, group_id)
    ensure_can_manage_group(teacher, group)
    return serialize_location(group)


@router.put("/groups/{group_id}/location")
def set_location(
    group_id: int,
    body: LocationIn,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> dict:
    """Nastaví geofence učebny podle aktuální polohy vyučujícího (je třeba být ve třídě)."""
    group = _get_group(db, group_id)
    ensure_can_manage_group(teacher, group)
    group.latitude, group.longitude, group.geofence_radius_m = body.latitude, body.longitude, body.radius_m
    db.commit()
    return serialize_location(group)


@router.delete("/groups/{group_id}/location")
def clear_location(group_id: int, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> dict:
    group = _get_group(db, group_id)
    ensure_can_manage_group(teacher, group)
    group.latitude = group.longitude = group.geofence_radius_m = None
    db.commit()
    return serialize_location(group)


@router.get("/me/groups")
def my_groups(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    """Skupiny, které uživatel vyučuje, nebo do nich je zapsán."""
    taught = db.scalars(select(Group).where(Group.teacher_id == user.id)).all()
    enrolled = db.scalars(
        select(Group).join(Enrollment, Enrollment.group_id == Group.id).where(Enrollment.user_id == user.id)
    ).all()
    result = {}
    for g in taught:
        result[g.id] = {"id": g.id, "course_id": g.course_id, "name": g.name, "role": "teacher"}
    for g in enrolled:
        result.setdefault(g.id, {"id": g.id, "course_id": g.course_id, "name": g.name, "role": "student"})
    return sorted(result.values(), key=lambda g: g["id"])


@router.post("/groups/{group_id}/students/import")
async def import_students(
    group_id: int,
    request: Request,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> dict:
    """Import studentů z CSV (hlavička: email,name). Účty bez hesla vznikají jako studentské."""
    group = _get_group(db, group_id)
    ensure_can_manage_group(teacher, group)

    raw = (await request.body()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    if reader.fieldnames is None or "email" not in [f.strip().lower() for f in reader.fieldnames]:
        raise HTTPException(status_code=400, detail="CSV musí obsahovat sloupec 'email'")

    created = enrolled = skipped = 0
    for row in reader:
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        email = row.get("email", "").lower()
        if not email or "@" not in email:
            skipped += 1
            continue
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, name=row.get("name", ""), role="student")
            db.add(user)
            db.flush()
            created += 1
        if db.get(Enrollment, (user.id, group.id)) is None:
            db.add(Enrollment(user_id=user.id, group_id=group.id))
            enrolled += 1
    db.commit()
    return {"created_users": created, "enrolled": enrolled, "skipped_rows": skipped}


@router.post("/groups/{group_id}/sessions", status_code=201)
def create_session(
    group_id: int,
    body: SessionIn,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> dict:
    group = _get_group(db, group_id)
    ensure_can_manage_group(teacher, group)
    starts, ends = to_naive_utc(body.starts_at), to_naive_utc(body.ends_at)
    if ends <= starts:
        raise HTTPException(status_code=422, detail="Konec hodiny musí být po začátku")
    lesson = LessonSession(group_id=group.id, starts_at=starts, ends_at=ends, status="ready")
    db.add(lesson)
    db.commit()
    return serialize_lesson(lesson)


@router.get("/groups/{group_id}/sessions")
def list_sessions(group_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    group = _get_group(db, group_id)
    if group.teacher_id != user.id and user.role != "admin" and db.get(Enrollment, (user.id, group_id)) is None:
        raise HTTPException(status_code=403, detail="Do skupiny nejste zapsáni")
    lessons = db.scalars(
        select(LessonSession).where(LessonSession.group_id == group_id).order_by(LessonSession.starts_at)
    ).all()
    return [serialize_lesson(l) for l in lessons]


def get_lesson_or_404(db: Session, session_id: int) -> LessonSession:
    lesson = db.get(LessonSession, session_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Hodina neexistuje")
    return lesson
