"""تنظیمات برنامه. همه از متغیر محیطی خوانده می‌شوند (pydantic-settings).

نام هر فیلد همان نام متغیر محیطی است (بدون حساسیت به بزرگی حروف)،
مثلا database_url از DATABASE_URL.
"""
import logging
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("behoosh.config")

# توکن‌هایی که از فایل نمونه کپی شده‌اند. با این‌ها مسیر توکن ثابت قدیمی باز نمی‌شود.
_WEAK_TOKENS = {"", "change-me", "changeme", "change_me", "secret", "token"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = "postgresql+psycopg://behoosh:behoosh@db:5432/behoosh"
    api_token: str = ""
    # سازگاری: توکن ثابت قدیمی. تا وقتی true است، API_TOKEN با scope سلامت کار می‌کند.
    auth_legacy_token: bool = True
    api_port: int = 8000
    timezone: str = "Asia/Tehran"

    # امنیت
    # لیست origin مجاز، جدا با ویرگول. "*" یعنی همه (توکن در هدر است نه کوکی).
    cors_origins: str = "*"
    # ثبت‌نام آزاد. داشبورد فرم ثبت‌نام ندارد؛ کاربر با app.db.set_password ساخته می‌شود.
    allow_registration: bool = False
    # عمر توکن ورود داشبورد. صفر یعنی بی‌انقضا.
    session_ttl_days: int = 30
    # سقف تلاش ورود/ثبت‌نام در هر پنجره، برای هر IP و هر ایمیل.
    auth_rate_limit: int = 10
    auth_rate_window_s: int = 300

    # اهداف پیش‌فرض
    default_kcal_target: float = 2400
    default_protein_target: float = 150
    default_sleep_target: float = 7.5
    default_screen_target_min: int = 240
    default_instagram_target_min: int = 90

    # کاربر اولیه seed
    seed_display_name: str = "کاربر"

    @field_validator("api_token")
    @classmethod
    def _strip(cls, v: str) -> str:
        return (v or "").strip()

    @property
    def legacy_token_enabled(self) -> bool:
        """توکن ثابت فقط وقتی فعال است که روشن باشد و مقدار نمونه نباشد."""
        return self.auth_legacy_token and self.api_token.lower() not in _WEAK_TOKENS

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()] or ["*"]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.auth_legacy_token and not s.legacy_token_enabled:
        log.warning("API_TOKEN خالی یا مقدار نمونه است؛ توکن ثابت قدیمی غیرفعال شد.")
    return s
