"""وابستگی‌های احراز هویت.

قاعده طلایی: user_id همیشه از توکن خوانده می‌شود و هرگز پارامتر ورودی نیست.
این تنها تضمینی است که یک توکن نمی‌تواند داده کاربر دیگر را ببیند.

سازگاری: توکن ثابت قدیمی (settings.api_token) هنوز کار می‌کند تا ثبت‌های
روزانه سلامت قطع نشوند. به‌محض اینکه توکن‌های واقعی ساخته شدند، آن را
با AUTH_LEGACY_TOKEN=false خاموش کن.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_token
from app.db.auth_models import ApiToken
from app.db.session import get_db

SCOPE_HEALTH_READ = "health:read"
SCOPE_HEALTH_WRITE = "health:write"
SCOPE_FINANCE_READ = "finance:read"
SCOPE_FINANCE_WRITE = "finance:write"
SCOPE_MEETING_READ = "meeting:read"
SCOPE_MEETING_WRITE = "meeting:write"
ALL_SCOPES = (
    SCOPE_HEALTH_READ, SCOPE_HEALTH_WRITE, SCOPE_FINANCE_READ, SCOPE_FINANCE_WRITE,
    SCOPE_MEETING_READ, SCOPE_MEETING_WRITE,
)


@dataclass
class Principal:
    """هویت تماس‌گیرنده. از توکن ساخته می‌شود، نه از ورودی."""
    user_id: object
    scopes: set = field(default_factory=set)
    token_id: object | None = None
    kind: str = "api"

    def has(self, scope: str) -> bool:
        return scope in self.scopes or "*" in self.scopes


def _extract_token(x_api_key: str | None, authorization: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def get_principal(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    """هویت را از توکن می‌سازد. توکن خام هرگز در دیتابیس نیست، فقط هش."""
    raw = _extract_token(x_api_key, authorization)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing token")

    settings = get_settings()

    # مسیر سازگاری: توکن ثابت قدیمی. بعد از انتقال کامل، خاموش شود.
    if settings.auth_legacy_token and raw == settings.api_token:
        from app.db.models import User
        uid = db.execute(select(User.id).order_by(User.created_at)).scalars().first()
        if not uid:
            raise HTTPException(400, "no user configured")
        # کمینه دسترسی: توکن ثابت قدیمی فقط سلامت. مالی توکن جدا دارد.
        return Principal(user_id=uid,
                         scopes={SCOPE_HEALTH_READ, SCOPE_HEALTH_WRITE},
                         kind="legacy")

    row = db.execute(
        select(ApiToken).where(ApiToken.token_hash == hash_token(raw))
    ).scalar_one_or_none()
    if row is None or row.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    if row.expires_at and row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token expired")

    row.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return Principal(user_id=row.user_id, scopes=set(row.scopes or []),
                     token_id=row.id, kind=row.kind)


def require_scope(scope: str):
    """وابستگی کارخانه‌ای: مسیر فقط با scope لازم باز می‌شود."""
    def _dep(p: Principal = Depends(get_principal)) -> Principal:
        if not p.has(scope):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"missing scope: {scope}")
        return p
    return _dep
