"""Настройки приложения из окружения / .env (pydantic-settings)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Подключение к PostgreSQL (драйвер psycopg3 работает и в sync, и в async режиме)
    database_url: str = "postgresql+psycopg://kitfinder:kitfinder@localhost:5432/kitfinder"

    # Аутентификация админа
    admin_password_hash: str = ""
    secret_key: str = "dev-insecure-secret-change-me"
    cookie_secure: bool = False  # True в проде (HTTPS)
    login_fail_delay_seconds: float = 1.0  # анти-брутфорс пауза при неверном пароле

    # S3-совместимое хранилище фото китов. Бакет должен допускать public-read
    # (или отдаваться через CDN) — фото раздаются по s3_public_base_url/<key>.
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "ru-central1"
    s3_public_base_url: str = ""  # напр. https://<bucket>.storage.yandexcloud.net


settings = Settings()
