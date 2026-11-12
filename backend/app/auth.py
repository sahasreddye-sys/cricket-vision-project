"""Built-in accounts: scrypt password hashes and signed JWT session tokens."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .models import User, get_db

_bearer = HTTPBearer(auto_error=False)
_N, _R, _P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=_N, r=_R, p=_P, dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(digest))
    except Exception:
        return False


def make_token(user: User) -> str:
    exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=settings.token_hours)
    return jwt.encode({"sub": str(user.id), "exp": exp}, settings.resolved_secret(), algorithm="HS256")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)) -> User:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    try:
        payload = jwt.decode(cred.credentials, settings.resolved_secret(), algorithms=["HS256"])
        user = db.get(User, int(payload["sub"]))
    except Exception:
        user = None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Sign in again.")
    return user


def coach_only(user: User = Depends(current_user)) -> User:
    if user.role not in ("admin", "coach"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a coach or team admin can do this.")
    return user


def admin_only(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the team admin can do this.")
    return user


def can_edit_player(user: User, player_id: int) -> None:
    """Coaches edit anyone; a player edits only their own records."""
    if user.role in ("admin", "coach") or user.player_id == player_id:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only add records for your own player profile.")
