"""مسیرهای سلامت زیر /v1.

نوشتن scope health:write می‌خواهد؛ خواندن با health:read یا health:write باز است.
user_id همیشه از توکن خوانده می‌شود.
"""
from fastapi import APIRouter

from app.api.health import insights, logs, temperament

router = APIRouter(prefix="/v1", tags=["health"])
router.include_router(logs.router)
router.include_router(temperament.router)
router.include_router(insights.router)
