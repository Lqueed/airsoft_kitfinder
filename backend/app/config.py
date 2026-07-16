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


settings = Settings()
