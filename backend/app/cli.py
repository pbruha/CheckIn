"""Správa účtů z příkazové řádky (náhrada za administrátorské rozhraní ve verzi MVP).

Použití:
    python -m app.cli create-user --email ucitel@skola.cz --name "Jana Nováková" --role teacher --password tajne
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from .config import load_settings
from .db import Base, make_session_factory
from .models import ROLES, User
from .security import hash_password


def create_user(email: str, name: str, role: str, password: str | None) -> None:
    settings = load_settings()
    engine, session_factory = make_session_factory(settings.database_url)
    Base.metadata.create_all(engine)
    email = email.strip().lower()
    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email)
            db.add(user)
        user.name = name or user.name
        user.role = role
        if password:
            user.password_hash = hash_password(password)
        db.commit()
        print(f"Uživatel {user.email} uložen (role: {user.role}, id: {user.id})")


def purge(before: str, scrub_days: int | None) -> None:
    from datetime import datetime

    from .retention import cutoff_for_days, purge_before, scrub_audit
    from .services import utcnow

    settings = load_settings()
    engine, session_factory = make_session_factory(settings.database_url)
    Base.metadata.create_all(engine)
    with session_factory() as db:
        counts = purge_before(db, datetime.fromisoformat(before), settings)
        print(f"Smazáno: {counts}")
        if scrub_days is not None:
            n = scrub_audit(db, cutoff_for_days(utcnow(), scrub_days))
            print(f"Vynulována IP a otisky zařízení u {n} záznamů starších než {scrub_days} dní")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="checkin")
    sub = parser.add_subparsers(dest="command", required=True)
    cu = sub.add_parser("create-user", help="vytvoří nebo upraví účet")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", default="")
    cu.add_argument("--role", choices=ROLES, default="teacher")
    cu.add_argument("--password", help="nastaví nebo změní heslo")
    pg = sub.add_parser("purge", help="smaže data hodin před daným datem (konec akademického roku)")
    pg.add_argument("--before", required=True, help="YYYY-MM-DD nebo ISO datum, např. 2027-02-01")
    pg.add_argument("--scrub-audit-days", type=int, default=None,
                    help="zároveň vynuluje IP a otisky zařízení u záznamů starších než N dní")
    args = parser.parse_args(argv)

    if args.command == "create-user":
        create_user(args.email, args.name, args.role, args.password)
    elif args.command == "purge":
        purge(args.before, args.scrub_audit_days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
