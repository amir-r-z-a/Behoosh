"""کلاینت HTTP مشترک سرورهای MCP بهوش.

هر تول MCP یک درخواست به API می‌زند و توکن خود کاربر (از هدر MCP) را می‌فرستد.
"""
import json
import os

import httpx

from app.mcp import _auth


def api_base() -> str:
    return os.getenv("BEHOOSH_API", "http://api:8000").rstrip("/")


def request(method: str, path: str, body: dict | None = None, params: dict | None = None,
            timeout: float = 30, raise_errors: bool = False):
    """درخواست به {API}/v1{path}.

    raise_errors=True: خطای HTTP به‌صورت استثنا بالا می‌رود (تول MCP خطا می‌دهد).
    raise_errors=False: خطا به‌صورت {"ok": False, "status", "error"} برمی‌گردد.
    """
    r = httpx.request(method, f"{api_base()}/v1{path}", json=body, params=params,
                      headers={"X-API-Key": _auth.current_token()}, timeout=timeout)
    if raise_errors:
        r.raise_for_status()
    elif r.status_code >= 400:
        return {"ok": False, "status": r.status_code, "error": r.text[:400]}
    return r.json()


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)
