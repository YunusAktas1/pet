from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlmodel import Session, select

from backend.core.config import settings
from backend.core.security import create_access_token
from backend.models.refresh_token import RefreshToken
from backend.models.user import User


def _now() -> datetime:
    return datetime.utcnow()


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _new_refresh_token(user_id: int) -> tuple[str, RefreshToken]:
    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw_token)
    expires_at = _now() + timedelta(days=settings.refresh_token_expire_days)
    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    return raw_token, refresh_token


def issue_tokens(session: Session, user: User) -> dict[str, str]:
    if user.id is None or user.email is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User record missing identifier",
        )

    raw_refresh_token, refresh_model = _new_refresh_token(user.id)
    try:
        session.add(refresh_model)
        session.commit()
        session.refresh(refresh_model)
    except Exception:
        session.rollback()
        raise

    access_token = create_access_token(sub=user.email)
    return {
        "access_token": access_token,
        "refresh_token": raw_refresh_token,
        "token_type": "bearer",
    }


def rotate_refresh_token(session: Session, provided_token: str) -> dict[str, str]:
    token_hash = _hash_token(provided_token)
    token_row = session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()

    if token_row is None or token_row.revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    now = _now()
    if token_row.expires_at <= now:
        token_row.revoked = True
        session.add(token_row)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    user = session.get(User, token_row.user_id)
    if user is None or user.email is None:
        token_row.revoked = True
        session.add(token_row)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    token_row.revoked = True
    new_raw_token, new_refresh_row = _new_refresh_token(token_row.user_id)
    try:
        session.add(token_row)
        session.add(new_refresh_row)
        session.commit()
        session.refresh(new_refresh_row)
    except Exception:
        session.rollback()
        raise

    access_token = create_access_token(sub=user.email)
    return {
        "access_token": access_token,
        "refresh_token": new_raw_token,
        "token_type": "bearer",
    }
