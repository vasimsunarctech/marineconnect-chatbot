import hashlib
import logging
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.personal_access_tokens import PersonalAccessToken

logger = logging.getLogger("authenticate")
auth_scheme = HTTPBearer(bearerFormat="Token")


def hash_sanctum_token(plain_token: str) -> str:
    """
    Laravel Sanctum stores SHA256(randomPart) where client sends "id|randomPart".
    So if token contains '|', hash only the part after the first pipe.
    """
    if not plain_token:
        return ""
    # token format: "<id>|<randomPart>"
    if '|' in plain_token:
        _, random_part = plain_token.split('|', 1)
    else:
        # fallback: some tokens may be plain; hash whole value
        random_part = plain_token
    return hashlib.sha256(random_part.encode("utf-8")).hexdigest()


async def authenticate(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db),
):
    """
    Validates a Sanctum personal access token.
    Returns User (ORM) if valid, raises HTTP errors otherwise.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    plain_token = credentials.credentials.strip()
    token_hash = hash_sanctum_token(plain_token)

    try:
        pat = db.execute(
            select(PersonalAccessToken).where(PersonalAccessToken.token == token_hash)
        ).scalars().first()
    except ProgrammingError as exc:
        logger.exception("DB error querying personal_access_tokens: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Auth DB error: ensure 'personal_access_tokens' table exists, migrations run, "
                "and DB user has SELECT permission."
            ),
        )

    if not pat:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if getattr(pat, "expires_at", None):
        expires_at = pat.expires_at
        if expires_at and expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")

    if pat.tokenable_type and "User" not in pat.tokenable_type:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token not valid for users")

    try:
        if hasattr(pat, "last_used_at"):
            pat.last_used_at = datetime.now(timezone.utc)
            db.add(pat)
            db.commit()
    except Exception:
        db.rollback()

    user = db.execute(select(User).where(User.id == pat.tokenable_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token owner not found")

    return user
