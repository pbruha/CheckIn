from __future__ import annotations

import os
from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import Attendance, Excuse, LessonSession
from app.retention import purge_before, scrub_audit
from conftest import DEVICE_A, T0, login, make_user
from test_api import classroom, checkin, qr, start  # noqa: F401


def test_purge_removes_old_lessons_with_attachments_and_keeps_recent(app, client, classroom, clock, settings):
    # stará hodina s docházkou, omluvenkou a přílohou
    start(client, classroom)
    checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=qr(client, classroom))
    os.makedirs(settings.upload_dir, exist_ok=True)
    with open(os.path.join(settings.upload_dir, "stara.pdf"), "wb") as fh:
        fh.write(b"%PDF")
    with app.state.session_factory() as db:
        from app.models import User
        bob_id = db.scalar(select(User.id).where(User.email == "bob@skola.cz"))
        db.add(Excuse(user_id=bob_id, session_id=classroom["lesson"]["id"], text="stará omluvenka",
                      status="pending", created_at=T0, attachment_path="stara.pdf",
                      attachment_name="stara.pdf", attachment_type="application/pdf"))
        db.commit()

    # nová hodina, která má zůstat
    recent_start = T0 + timedelta(days=200)
    with app.state.session_factory() as db:
        db.add(LessonSession(group_id=classroom["group"]["id"], starts_at=recent_start,
                             ends_at=recent_start + timedelta(hours=1), status="ready"))
        db.commit()

    with app.state.session_factory() as db:
        counts = purge_before(db, T0 + timedelta(days=30), settings)
    assert counts["sessions"] == 1 and counts["excuses"] == 1 and counts["attachments"] == 1
    assert counts["attendance"] >= 1
    assert not os.path.exists(os.path.join(settings.upload_dir, "stara.pdf"))
    with app.state.session_factory() as db:
        remaining = db.scalars(select(LessonSession.starts_at)).all()
        assert remaining == [recent_start]
        assert db.scalars(select(Attendance)).all() == []


def test_scrub_clears_ip_and_device_for_old_records(app, client, classroom, clock):
    start(client, classroom)
    checkin(client, classroom, "alice@skola.cz", DEVICE_A, qr_token=qr(client, classroom))
    with app.state.session_factory() as db:
        record = db.scalar(select(Attendance))
        record.ip = "10.0.0.5"
        db.commit()
        assert record.device_hash is not None
    with app.state.session_factory() as db:
        assert scrub_audit(db, T0 + timedelta(days=1)) == 1
    with app.state.session_factory() as db:
        record = db.scalar(select(Attendance))
        assert record.ip is None and record.device_hash is None and record.status == "present"


def test_migrations_match_models(tmp_path, monkeypatch):
    """Schéma vytvořené migracemi musí odpovídat modelům (jinak chybí migrace)."""
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine

    from app.db import Base
    from app import models  # noqa: F401

    backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    url = f"sqlite:///{tmp_path / 'mig.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config(os.path.join(backend, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(backend, "migrations"))
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], diff
