from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

ROLES = ("student", "teacher", "admin")
SESSION_STATUSES = ("ready", "running", "closed")
ATTENDANCE_STATUSES = ("present", "late", "absent", "excused")
METHODS = ("qr", "code", "manual", "auto", "excuse")
EXCUSE_STATUSES = ("pending", "approved", "rejected")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(20), default="student")
    # Studenti bez hesla se mohou přihlásit až po SSO integraci (verze 3).
    password_hash: Mapped[str | None] = mapped_column(String(300), nullable=True)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    semester: Mapped[str] = mapped_column(String(50), default="")


class Group(Base):
    """Skupina (cvičení) předmětu. Vyučující je tvůrce skupiny."""

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    name: Mapped[str] = mapped_column(String(200))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # Geofence učebny: souřadnice a poloměr v metrech. Pokud chybí, ověření polohy je vypnuté.
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geofence_radius_m: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Enrollment(Base):
    __tablename__ = "enrollments"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)


class LessonSession(Base):
    """Jedna hodina (session) skupiny. Tabulka se jmenuje kvůli kolizi se SQLAlchemy Session."""

    __tablename__ = "lesson_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="ready")
    # Číselný kód je dočasný a ukládá se jen na dobu platnosti.
    code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (Index("ix_attendance_session_device", "session_id", "device_hash"),)

    session_id: Mapped[int] = mapped_column(ForeignKey("lesson_sessions.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    method: Mapped[str] = mapped_column(String(20))
    recorded_at: Mapped[datetime] = mapped_column(DateTime)
    device_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # HMAC, ne surový identifikátor
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Jen výsledek ověření polohy. Souřadnice studenta se neukládají.
    geo_verified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class Excuse(Base):
    """Omluvenka studenta k jedné hodině. Schválení nastaví stav „omluven“ v docházce."""

    __tablename__ = "excuses"
    __table_args__ = (UniqueConstraint("user_id", "session_id", name="uq_excuse_user_session"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("lesson_sessions.id"), index=True)
    text: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    attachment_path: Mapped[str | None] = mapped_column(String(300), nullable=True)  # relativní název v upload_dir
    attachment_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
