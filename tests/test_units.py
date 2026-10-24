"""تست‌های واحد بدون دیتابیس."""
from datetime import date
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.ratelimit import RateLimiter, client_ip
from app.core.security import hash_password, hash_token, new_token, verify_password
from app.services import jalali
from app.services.sms_parser import parse_sms


# ---------- security ----------

def test_password_roundtrip():
    h = hash_password("correct horse")
    assert h.startswith("scrypt$")
    assert verify_password("correct horse", h)
    assert not verify_password("wrong", h)
    assert not verify_password("x", "garbage")


def test_tokens_are_random_and_hashed():
    a, b = new_token(), new_token()
    assert a != b and a.startswith("bh_")
    assert hash_token(a) == hash_token(a) != a


# ---------- config ----------

@pytest.mark.parametrize("tok", ["", "CHANGE_ME", "change-me", "  change-me  "])
def test_placeholder_legacy_token_is_disabled(tok):
    assert not Settings(api_token=tok, auth_legacy_token=True).legacy_token_enabled


def test_real_legacy_token_enabled_only_when_switched_on():
    assert Settings(api_token="a-long-random-value", auth_legacy_token=True).legacy_token_enabled
    assert not Settings(api_token="a-long-random-value",
                        auth_legacy_token=False).legacy_token_enabled


def test_cors_origin_list():
    assert Settings(cors_origins="https://a.com, https://b.com").cors_origin_list == [
        "https://a.com", "https://b.com"]
    assert Settings(cors_origins="").cors_origin_list == ["*"]


# ---------- rate limit ----------

def test_rate_limiter_window():
    now = [0.0]
    rl = RateLimiter(2, 10, clock=lambda: now[0])
    assert rl.hit("k") and rl.hit("k")
    assert not rl.hit("k")
    assert rl.hit("other")
    now[0] = 10.0
    assert rl.hit("k")


def test_rate_limiter_zero_means_unlimited():
    rl = RateLimiter(0, 10)
    assert all(rl.hit("k") for _ in range(100))


def _req(peer, headers=None):
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers or {})


def test_client_ip_trusts_proxy_headers_only_from_private_peer():
    hdr = {"x-forwarded-for": "8.8.8.8, 10.0.0.1"}
    assert client_ip(_req("172.18.0.5", hdr)) == "8.8.8.8"
    assert client_ip(_req("127.0.0.1", {"x-real-ip": "9.9.9.9"})) == "9.9.9.9"
    # اتصال مستقیم از اینترنت: هدر جعلی نادیده گرفته می‌شود
    assert client_ip(_req("1.2.3.4", hdr)) == "1.2.3.4"


# ---------- jalali ----------

@pytest.mark.parametrize("g,j", [
    (date(2026, 3, 21), (1405, 1, 1)),
    (date(2026, 10, 17), (1405, 7, 25)),
    (date(2025, 3, 20), (1403, 12, 30)),  # ۱۴۰۳ کبیسه است
])
def test_jalali_roundtrip(g, j):
    assert jalali.gregorian_to_jalali(g) == j
    assert jalali.jalali_to_gregorian(*j) == g


def test_parse_date_accepts_both_calendars():
    assert jalali.parse_date("1405/07/25") == date(2026, 10, 17)
    assert jalali.parse_date("2026-10-17") == date(2026, 10, 17)
    assert jalali.to_jalali_str(date(2026, 10, 17)) == "1405/07/25"


# ---------- sms parser ----------

def test_sms_debit_in_rial_converted_to_toman():
    body = ("بانک ملت\nبرداشت مبلغ ۱,۲۵۰,۰۰۰ ریال\nاز کارت ****1234\n"
            "مانده: ۵,۰۰۰,۰۰۰ ریال\n1405/07/25\nشماره پیگیری: 987654")
    out = parse_sms(body)
    assert out["direction"] == "debit"
    assert out["amount"] == 125000
    assert out["unit"] == "rial"
    assert out["card_last4"] == "1234"
    assert out["balance"] == 500000
    assert out["external_ref"] == "sms:987654"
    assert out["occurred_at"].startswith("2026-10-17")


def test_sms_credit():
    out = parse_sms("واریز به حساب شما مبلغ 500,000 تومان")
    assert out["direction"] == "credit"
    assert out["amount"] == 500000


@pytest.mark.parametrize("body", ["", "سلام، کد تایید شما 1234 است", "مبلغ 1000 ریال"])
def test_sms_unsure_returns_none(body):
    assert parse_sms(body) is None
