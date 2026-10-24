"""وابستگی‌ها و کمک‌تابع‌های مشترک مسیرهای سلامت."""
from datetime import date, datetime, time

from fastapi import HTTPException

from app.api.auth_deps import (
    SCOPE_HEALTH_READ, SCOPE_HEALTH_WRITE, require_any_scope, require_scope,
)

# خواندن با هر کدام از دو scope باز است تا توکن‌های فقط-نوشتن قدیمی نشکنند.
HEALTH_READ = require_any_scope(SCOPE_HEALTH_READ, SCOPE_HEALTH_WRITE)
HEALTH_WRITE = require_scope(SCOPE_HEALTH_WRITE)


def _uid(p) -> str:
    """user_id از توکن می‌آید، نه از دیتابیس. مرز امنیتی."""
    return p.user_id


def _parse_dt(value: str | None, base: date) -> datetime | None:
    """رشته ساعت را به datetime تبدیل می‌کند. هم '23:30' هم ISO کامل."""
    if not value:
        return None
    v = value.strip()
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        pass
    try:
        t = time.fromisoformat(v)
        return datetime.combine(base, t)
    except ValueError:
        raise HTTPException(422, f"bad time format: {value!r} (use HH:MM or ISO)") from None
