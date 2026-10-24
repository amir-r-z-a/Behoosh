"""امنیت: هش رمز و توکن. فقط از کتابخانه استاندارد استفاده می‌کند تا وابستگی اضافه نشود.

هش رمز با scrypt (حافظه‌سخت، مقاوم به حمله گرافیک) و توکن به‌صورت تصادفی امن.
توکن هرگز خام ذخیره نمی‌شود؛ فقط sha256 آن در دیتابیس می‌ماند.
"""
import hashlib
import hmac
import secrets

_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DK_LEN = 32
_MAXMEM = 64 * 1024 * 1024


def hash_password(password: str) -> str:
    """رمز را با scrypt هش می‌کند. خروجی خودتوصیف است تا پارامترها قابل تغییر باشند."""
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_DK_LEN, maxmem=_MAXMEM,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """رمز را با هش ذخیره‌شده مقایسه می‌کند. مقایسه زمان‌ثابت."""
    try:
        algo, n, r, p, salt_hex, dk_hex = stored.split("$")
        if algo != "scrypt":
            return False
        expected = bytes.fromhex(dk_hex)
        dk = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(expected), maxmem=_MAXMEM,
        )
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False


def new_token(prefix: str = "bh") -> str:
    """توکن خام. فقط یک بار به کاربر نشان داده می‌شود."""
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def hash_token(token: str) -> str:
    """هش توکن برای ذخیره در دیتابیس."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
