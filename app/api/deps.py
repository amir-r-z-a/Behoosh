"""سازگاری مسیرهای سلامت.

مسیرهای سلامت قبلا با یک توکن ثابت کار می‌کردند. حالا از همان لایه احراز هویت
جدید استفاده می‌کنند تا هم توکن قدیمی (در دوره مهاجرت) و هم توکن‌های واقعی
scope‌دار کار کنند. این باعث می‌شود ثبت‌های روزانه سلامت قطع نشوند.

نکته: مسیرهای سلامت user_id را از توکن می‌خوانند، نه از دیتابیس.
"""
from fastapi import Depends

from app.api.auth_deps import (
    SCOPE_HEALTH_WRITE, Principal, get_principal, require_scope,
)


def require_token(p: Principal = Depends(require_scope(SCOPE_HEALTH_WRITE))) -> Principal:
    """جایگزین تابع قدیمی. حالا هویت واقعی برمی‌گرداند."""
    return p
