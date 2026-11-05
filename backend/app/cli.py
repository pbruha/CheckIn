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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="checkin")
    sub = parser.add_subparsers(dest="command", required=True)
    cu = sub.add_parser("create-user", help="vytvoří nebo upraví účet")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", default="")
    cu.add_argument("--role", choices=ROLES, default="teacher")
    cu.add_argument("--password", help="nastaví nebo změní heslo")
    args = parser.parse_args(argv)

    if args.command == "create-user":
        create_user(args.email, args.name, args.role, args.password)
    return 0


if __name__ == "__main__":
    sys.exit(main())
