import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        self.database_url: str = os.getenv(
            'DATABASE_URL',
            'postgresql+psycopg://behoosh:behoosh@db:5432/behoosh',
        )
        self.api_token: str = os.getenv('API_TOKEN', 'change-me')
        # سازگاری: توکن ثابت قدیمی. تا وقتی true است، API_TOKEN با همه scope ها کار می‌کند.
        self.auth_legacy_token: bool = (
            os.getenv('AUTH_LEGACY_TOKEN', 'true').strip().lower()
            in ('1', 'true', 'yes', 'on')
        )
        self.api_port: int = int(os.getenv('API_PORT', '8000'))
        self.timezone: str = os.getenv('TIMEZONE', 'Asia/Tehran')
        self.default_kcal_target: float = float(os.getenv('DEFAULT_KCAL_TARGET', '2400'))
        self.default_protein_target: float = float(os.getenv('DEFAULT_PROTEIN_TARGET', '150'))
        self.default_sleep_target: float = float(os.getenv('DEFAULT_SLEEP_TARGET', '7.5'))
        self.default_screen_target_min: int = int(os.getenv('DEFAULT_SCREEN_TARGET_MIN', '240'))
        self.default_instagram_target_min: int = int(os.getenv('DEFAULT_INSTAGRAM_TARGET_MIN', '90'))


@lru_cache
def get_settings() -> Settings:
    return Settings()
