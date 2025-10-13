from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

import jwt
from passlib.context import CryptContext

if __package__ is None or __package__ == "":
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from backend.core.config import settings

_ALGO: str = settings.jwt_algorithm

# Default: argon2 (bypasses bcrypt limits)
# Legacy verification order: argon2 > bcrypt_sha256 > bcrypt
_pwd = CryptContext(
    schemes=["argon2", "bcrypt_sha256", "bcrypt"],
    default="argon2",
    deprecated="auto",
)


def hash_password(raw: str) -> str:
    return cast(str, _pwd.hash(raw))


def verify_password(raw: str, hashed: str) -> bool:
    return cast(bool, _pwd.verify(raw, hashed))


def create_access_token(sub: str, *, minutes: int | None = None) -> str:
    minutes = minutes or settings.access_token_expire_minutes
    expire = datetime.utcnow() + timedelta(minutes=minutes)
    payload: dict[str, Any] = {"sub": sub, "exp": expire}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=_ALGO)
    return token


def decode_token(token: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[_ALGO],
        ),
    )
