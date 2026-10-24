"""محدودیت نرخ ساده در حافظه برای مسیرهای ورود و ثبت‌نام.

پنجره لغزان روی هر کلید (IP یا ایمیل). حالت فقط در همین پروسه است؛ برای
یک کانتینر API کافی است. اگر چند worker شد، باید به Redis منتقل شود.
"""
import ipaddress
import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, limit: int, window_s: float, clock=time.monotonic):
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        """یک تلاش ثبت می‌کند. اگر از سقف گذشته باشد False برمی‌گرداند."""
        if self.limit <= 0:
            return True
        now = self._clock()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] >= self.window_s:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            if len(self._hits) > 10_000:
                self._prune(now)
            return True

    def _prune(self, now: float) -> None:
        for k in [k for k, q in self._hits.items() if not q or now - q[-1] >= self.window_s]:
            del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def check(self, *keys: str) -> None:
        """همه کلیدها را می‌شمارد و اگر یکی از سقف گذشت ۴۲۹ می‌دهد."""
        results = [self.hit(k) for k in keys if k]
        if not all(results):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                "too many attempts, try again later",
                                headers={"Retry-After": str(int(self.window_s))})


def _is_private(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback


def client_ip(request: Request) -> str:
    """IP واقعی کاربر.

    هدرهای پروکسی فقط وقتی پذیرفته می‌شوند که خود اتصال از شبکه داخلی
    (Caddy/Nginx روی همان سرور یا شبکه داکر) آمده باشد؛ وگرنه قابل جعل‌اند.
    """
    peer = request.client.host if request.client else ""
    if _is_private(peer):
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
    return peer
