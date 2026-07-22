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
    # Дефолты — под локальный MinIO из docker-compose (в проде переопределить в .env).
    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "kit-images"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    s3_public_base_url: str = "http://localhost:9000/kit-images"


settings = Settings()
