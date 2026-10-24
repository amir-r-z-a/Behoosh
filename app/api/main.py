"""نقطه ورود FastAPI.

سه گروه مسیر:
- /v1/auth/*     : ثبت‌نام، ورود، توکن. بدون احراز هویت باز است.
- /v1/health/*   : سلامت. سازگاری: مسیرهای قدیمی بدون prefix هم کار می‌کنند.
- /v1/finance/*  : مالی. scope جدا از سلامت.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth_routes import router as auth_router
from app.api.finance_routes import read as fin_read, write as fin_write
from app.api.health import router
from app.api.dashboard import router as dash_router
from app.api.live_routes import router as live_router
from app.core.config import get_settings

app = FastAPI(title="بهوش", version="0.2.0",
              description="پلتفرم سلامت و مالی شخصی")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(router)
app.include_router(fin_read)
app.include_router(fin_write)
app.include_router(dash_router)
app.include_router(live_router)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "behoosh", "version": "0.2.0",
            "modules": ["health", "finance", "auth", "live"]}
