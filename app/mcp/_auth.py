"""احراز هویت MCP بهوش.

توکن کاربر از هدر درخواست خوانده می‌شود: Authorization: Bearer <token> یا X-API-Key.
اگر هدر نبود، فقط وقتی MCP_ALLOW_FALLBACK=true باشد از توکن محیطی استفاده می‌شود.
این‌طور هر ایجنت با توکن خودِ کاربر وصل می‌شود و دسترسی جداگانه است.
"""
import contextvars
import os

_token_var = contextvars.ContextVar("behoosh_user_token", default=None)

ENV_TOKEN = None


def set_env_token(t):
    global ENV_TOKEN
    ENV_TOKEN = t


def _allow_fallback():
    return os.getenv("MCP_ALLOW_FALLBACK", "false").strip().lower() in ("1", "true", "yes")


def current_token():
    t = _token_var.get()
    if t:
        return t
    if _allow_fallback() and ENV_TOKEN:
        return ENV_TOKEN
    raise PermissionError(
        "توکن کاربر پیدا نشد. در تنظیمات MCP کلاینت، هدر "
        "'Authorization: Bearer <token>' را اضافه کن."
    )


class TokenHeaderMiddleware:
    """توکن را از هدر HTTP می‌خواند و در contextvar می‌گذارد."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            tok = None
            for k, v in scope.get("headers", []):
                if k == b"authorization":
                    s = v.decode("latin-1").strip()
                    tok = s[7:].strip() if s[:7].lower() == "bearer " else s
                    break
                if k == b"x-api-key":
                    tok = v.decode("latin-1").strip()
            _token_var.set(tok)  # اگر هدر نبود، None می‌شود تا توکن قبلی نشتی نکند
        await self.app(scope, receive, send)


def serve(mcp, port):
    import uvicorn
    app = mcp.streamable_http_app()
    app.add_middleware(TokenHeaderMiddleware)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
