"""Run once with local .env configured; never publish credentials."""
import getpass
import os
from sqlalchemy import select
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.models.document import User
from app.core.security import hash_password

def main():
    if settings.jwt_secret in {"development-only-change-this-secret", "replace_with_a_long_random_secret"} or len(settings.jwt_secret) < 32:
        raise SystemExit("Set a unique JWT_SECRET (at least 32 characters) in .env first.")
    Base.metadata.create_all(bind=engine)
    name = input("Administrator username [admin]: ").strip() or "admin"
    if not (3 <= len(name) <= 120):
        raise SystemExit("Username must have 3-120 characters")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == name)):
            raise SystemExit("User already exists; no account was changed")
        pw = getpass.getpass("New administrator password (at least 12 characters): ")
        if len(pw) < 12:
            raise SystemExit("Password is too short")
        db.add(User(username=name, password_hash=hash_password(pw), role="admin", department="general"))
        db.commit()
    print("Administrator created. Do not share the password.")

if __name__ == "__main__":
    main()
