"""اجرای مایگریشن‌های SQL به ترتیب نام فایل.

کاربرد:
    python -m app.db.migrate            # اجرای مایگریشن‌های اجرانشده
    python -m app.db.migrate --status   # فقط نمایش وضعیت

هر فایل در تراکنش خودش اجرا و در جدول schema_migrations ثبت می‌شود.
همه فایل‌ها idempotent نوشته شده‌اند (IF NOT EXISTS)، پس روی دیتابیسی که
قبلا دستی مایگریت شده هم بی‌خطر اجرا می‌شوند و فقط ثبت می‌شوند.
قفل advisory جلوی اجرای همزمان دو کانتینر را می‌گیرد.
"""
import argparse
import hashlib
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
# کلید ثابت قفل advisory. فقط باید در این دیتابیس یکتا باشد.
_LOCK_KEY = 7_204_311

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  filename TEXT PRIMARY KEY,
  checksum TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now())
"""


def migration_files(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    return sorted(directory.glob("*.sql"), key=lambda p: p.name)


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def applied(engine: Engine) -> dict[str, str]:
    with engine.begin() as conn:
        conn.exec_driver_sql(_CREATE_TABLE)
        rows = conn.execute(text("SELECT filename, checksum FROM schema_migrations")).all()
    return {f: c for f, c in rows}


def migrate(engine: Engine, directory: Path = MIGRATIONS_DIR, log=print) -> list[str]:
    """مایگریشن‌های اجرانشده را اجرا می‌کند و نام‌شان را برمی‌گرداند."""
    ran: list[str] = []
    with engine.connect() as lock_conn:
        lock_conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _LOCK_KEY})
        try:
            done = applied(engine)
            for path in migration_files(directory):
                digest = _checksum(path)
                if path.name in done:
                    if done[path.name] != digest:
                        log(f"warning: {path.name} changed after it was applied; not re-running")
                    continue
                with engine.begin() as conn:
                    conn.exec_driver_sql(path.read_text(encoding="utf-8"))
                    conn.execute(
                        text("INSERT INTO schema_migrations (filename, checksum) "
                             "VALUES (:f, :c)"), {"f": path.name, "c": digest})
                log(f"applied {path.name}")
                ran.append(path.name)
        finally:
            lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _LOCK_KEY})
            lock_conn.commit()
    return ran


def main() -> int:
    ap = argparse.ArgumentParser(description="Behoosh SQL migrations")
    ap.add_argument("--status", action="store_true", help="show status without applying")
    args = ap.parse_args()

    engine = create_engine(get_settings().database_url, future=True)
    if args.status:
        done = applied(engine)
        for path in migration_files():
            print(f"{'applied' if path.name in done else 'pending'}  {path.name}")
        return 0
    ran = migrate(engine)
    print(f"{len(ran)} migration(s) applied" if ran else "database is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
