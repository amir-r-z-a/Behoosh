"""پیکربندی تست‌ها.

تست‌های API به یک Postgres واقعی نیاز دارند (UUID، JSONB، اسکیمای finance/live).
آدرس را در TEST_DATABASE_URL بده؛ دیتابیس پاک و از نو مایگریت می‌شود. اگر نبود،
فقط تست‌های واحد اجرا می‌شوند.
"""
import os

import pytest

TEST_DB = os.getenv("TEST_DATABASE_URL")
LEGACY_TOKEN = "test-legacy-token-0123456789"

# باید قبل از import برنامه تنظیم شود؛ engine هنگام import ساخته می‌شود.
if TEST_DB:
    os.environ["DATABASE_URL"] = TEST_DB
os.environ["API_TOKEN"] = LEGACY_TOKEN
os.environ.setdefault("ALLOW_REGISTRATION", "true")


@pytest.fixture(scope="session")
def engine():
    if not TEST_DB:
        pytest.skip("TEST_DATABASE_URL not set")
    from sqlalchemy import text

    from app.db.migrate import migrate
    from app.db.session import engine as eng

    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS live CASCADE"))
        conn.execute(text("DROP SCHEMA IF EXISTS finance CASCADE"))
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    migrate(eng, log=lambda _msg: None)
    return eng


@pytest.fixture
def client(engine):
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.api.auth_routes import limiter
    from app.api.main import app

    # همه جدول‌های کاربری به users وصل‌اند و با CASCADE پاک می‌شوند.
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE users CASCADE"))
    limiter.reset()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def settings():
    from app.core.config import get_settings
    return get_settings()


def register_and_login(client, email="a@example.com", password="password123", name="A"):
    r = client.post("/v1/auth/register",
                    json={"email": email, "password": password, "display_name": name})
    assert r.status_code == 201, r.text
    r = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user(client):
    """کاربر واردشده با توکن همه scope ها."""
    data = register_and_login(client)
    return {**data, "headers": auth(data["token"])}
