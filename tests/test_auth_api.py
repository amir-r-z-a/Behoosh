"""احراز هویت، scope ها، جداسازی کاربران، محدودیت نرخ."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from tests.conftest import LEGACY_TOKEN, auth, register_and_login


def test_health_endpoint(client):
    assert client.get("/health").json()["ok"] is True


def test_register_disabled(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "allow_registration", False)
    r = client.post("/v1/auth/register", json={
        "email": "x@example.com", "password": "password123", "display_name": "X"})
    assert r.status_code == 403


def test_register_login_me(client):
    data = register_and_login(client, email="Me@Example.com")
    assert data["expires_at"] is not None
    me = client.get("/v1/auth/me", headers=auth(data["token"])).json()
    assert me["display_name"] == "A"
    assert "finance:write" in me["scopes"]


def test_duplicate_email_rejected(client):
    register_and_login(client)
    r = client.post("/v1/auth/register", json={
        "email": "A@example.com", "password": "password123", "display_name": "B"})
    assert r.status_code == 409


def test_wrong_password_and_missing_token(client):
    register_and_login(client)
    r = client.post("/v1/auth/login", json={"email": "a@example.com", "password": "nope-nope"})
    assert r.status_code == 401
    assert client.get("/v1/auth/me").status_code == 401
    assert client.get("/v1/auth/me", headers=auth("bh_bogus")).status_code == 401


def test_login_rate_limited(client):
    register_and_login(client)  # ثبت‌نام و ورود دو تلاش از سقف ۱۰ را مصرف کردند
    codes = [client.post("/v1/auth/login", json={
        "email": "a@example.com", "password": "bad-password"}).status_code for _ in range(10)]
    assert codes == [401] * 8 + [429] * 2


def test_expired_session_token(client, engine):
    from sqlalchemy.orm import Session

    from app.db.auth_models import ApiToken

    data = register_and_login(client)
    with Session(engine) as db:
        db.execute(update(ApiToken).values(
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.commit()
    r = client.get("/v1/auth/me", headers=auth(data["token"]))
    assert r.status_code == 401
    assert r.json()["detail"] == "token expired"


def test_create_and_revoke_scoped_token(client, user):
    r = client.post("/v1/auth/tokens", headers=user["headers"],
                    json={"name": "agent", "scopes": ["health:read"]})
    assert r.status_code == 201
    tok = r.json()
    h = auth(tok["token"])

    # health:read کافی است برای خواندن، نه نوشتن، نه مالی
    assert client.get("/v1/day_summary", headers=h).status_code == 200
    assert client.post("/v1/log_mood", headers=h,
                       json={"log_date": "2026-10-20", "mood": 5}).status_code == 403
    assert client.get("/v1/finance/accounts", headers=h).status_code == 403

    listed = client.get("/v1/auth/tokens", headers=user["headers"]).json()["tokens"]
    assert any(t["id"] == tok["id"] for t in listed)
    assert "token" not in listed[0]

    assert client.delete(f"/v1/auth/tokens/{tok['id']}",
                         headers=user["headers"]).status_code == 200
    assert client.get("/v1/day_summary", headers=h).status_code == 401


def test_write_only_token_can_still_read_health(client, user):
    """توکن‌های قدیمی ایجنت فقط health:write داشتند و با آن می‌خواندند."""
    tok = client.post("/v1/auth/tokens", headers=user["headers"],
                      json={"scopes": ["health:write"]}).json()["token"]
    assert client.get("/v1/meals", params={"d": "2026-10-20"},
                      headers=auth(tok)).status_code == 200


def test_unknown_or_escalated_scopes_rejected(client, user):
    r = client.post("/v1/auth/tokens", headers=user["headers"], json={"scopes": ["admin"]})
    assert r.status_code == 400
    low = client.post("/v1/auth/tokens", headers=user["headers"],
                      json={"scopes": ["health:read"]}).json()["token"]
    r = client.post("/v1/auth/tokens", headers=auth(low), json={"scopes": ["finance:read"]})
    assert r.status_code == 403


def test_legacy_token(client, user, settings, monkeypatch):
    h = {"X-API-Key": LEGACY_TOKEN}
    assert client.get("/v1/day_summary", headers=h).status_code == 200
    # توکن ثابت فقط سلامت دارد
    assert client.get("/v1/finance/accounts", headers=h).status_code == 403
    monkeypatch.setattr(settings, "auth_legacy_token", False)
    assert client.get("/v1/day_summary", headers=h).status_code == 401


def test_users_cannot_touch_each_others_data(client, user):
    r = client.post("/v1/log_meal", headers=user["headers"], json={
        "log_date": "2026-10-20", "slot": "lunch",
        "items": [{"name": "برنج", "quantity": 200, "unit": "gram", "kcal": 260}]})
    assert r.status_code == 200
    meal_id = client.get("/v1/meals", params={"d": "2026-10-20"},
                         headers=user["headers"]).json()["items"][0]["id"]

    other = auth(register_and_login(client, email="b@example.com", name="B")["token"])
    assert client.get("/v1/meals", params={"d": "2026-10-20"},
                      headers=other).json()["count"] == 0
    assert client.delete(f"/v1/meals/{meal_id}", headers=other).status_code == 404
    assert client.patch(f"/v1/meals/{meal_id}", headers=other,
                        json={"kcal": 1}).status_code == 404
    assert client.get("/v1/day_summary", params={"d": "2026-10-20"},
                      headers=other).json()["kcal"] == 0
