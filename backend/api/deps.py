"""
Authentication + tenant context.

Production: `Authorization: Bearer <Supabase access token>`.
Development: if `AUTH_DISABLED=true` or no `SUPABASE_JWT_SECRET`, uses demo tenant (business_id=1).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from core.config import settings
from db.models import Business
from db.seed import seed_default_roles
from db.session import get_db

logger = logging.getLogger(__name__)

DEMO_USER_ID = "dev-ai-scheduler"


@dataclass
class AuthContext:
    user_id: str
    business_id: int
    is_dev_bypass: bool


def _get_or_create_business_for_owner(db: Session, owner_id: str, name: str = "My Business") -> Business:
    """Looked up by owner_user_id, not a hardcoded id — lets Postgres assign the PK
    normally so its sequence never desyncs from an explicit-id insert."""
    b = db.query(Business).filter(Business.owner_user_id == owner_id).first()
    if b:
        return b
    b = Business(owner_user_id=owner_id, name=name)
    db.add(b)
    db.commit()
    db.refresh(b)
    seed_default_roles(db, b.id)
    return b


def _ensure_demo_business(db: Session) -> int:
    b = _get_or_create_business_for_owner(db, DEMO_USER_ID, name="Demo Restaurant")
    return b.id


def authenticate(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> AuthContext:
    """Resolve Supabase user -> tenant business_id."""
    auth_disabled = settings.AUTH_DISABLED or not settings.SUPABASE_JWT_SECRET.strip()

    if auth_disabled:
        bid = _ensure_demo_business(db)
        logger.debug("Auth disabled — using demo business_id=%s", bid)
        return AuthContext(user_id=DEMO_USER_ID, business_id=bid, is_dev_bypass=True)

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization: Bearer <token>",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Empty bearer token")

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except InvalidTokenError as e:
        logger.info("JWT decode failed: %s", e)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from e

    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token missing sub")

    business = _get_or_create_business_for_owner(db, sub)
    return AuthContext(user_id=sub, business_id=business.id, is_dev_bypass=False)


AuthDep = Annotated[AuthContext, Depends(authenticate)]
