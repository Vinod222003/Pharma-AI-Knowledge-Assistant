from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.document import User

ROLES = {"admin", "regulatory", "medical", "quality", "viewer"}
SCHEME = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260000)
    return f"pbkdf2_sha256$260000${salt.hex()}${digest.hex()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds, salt, digest = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(candidate, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False

def create_token(username: str, role: str = "viewer") -> str:
    expiry = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": username, "exp": expiry}, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(SCHEME), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Please sign in", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        username = payload.get("sub")
        if not isinstance(username, str):
            raise ValueError("Invalid subject")
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = db.scalar(select(User).where(User.username == username, User.is_active == 1))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or disabled")
    return user

def allowed_departments(user: User) -> set[str]:
    if user.role == "admin":
        return {"general", "quality", "medical", "regulatory"}
    return {"general", user.department}

def require_editor(user: User) -> None:
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Editor permission required")
