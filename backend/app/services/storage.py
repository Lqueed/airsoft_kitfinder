"""S3-совместимое хранилище фото китов (boto3).

Синхронный клиент — в async-эндпоинтах вызывать через `run_in_threadpool`.
В тестах функции подменяются `monkeypatch` (реальный S3 не требуется).
"""

import mimetypes
import uuid
from functools import lru_cache

import boto3
from botocore.client import BaseClient

from app.config import settings

_PREFIX = "kit-images"
# Допустимые типы фото → расширение файла в ключе.
_EXT_BY_TYPE: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


@lru_cache(maxsize=1)
def _client() -> BaseClient:
    """Ленивый boto3 S3-клиент из настроек (кэшируется на процесс)."""
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.s3_access_key or None,
        aws_secret_access_key=settings.s3_secret_key or None,
        region_name=settings.s3_region or None,
    )


def is_allowed_type(content_type: str | None) -> bool:
    """True, если тип файла — поддерживаемое изображение."""
    return content_type in _EXT_BY_TYPE


def upload_image(data: bytes, content_type: str) -> str:
    """Загружает изображение в бакет, возвращает object key."""
    ext = _EXT_BY_TYPE.get(content_type) or mimetypes.guess_extension(content_type) or "bin"
    key = f"{_PREFIX}/{uuid.uuid4().hex}.{ext.lstrip('.')}"
    _client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)
    return key


def delete_object(key: str) -> None:
    """Удаляет объект из бакета (ошибки отсутствия объекта игнорируются S3)."""
    _client().delete_object(Bucket=settings.s3_bucket, Key=key)


def public_url(key: str) -> str:
    """Публичный URL объекта для витрины/админки (стабильный, не истекает)."""
    base = settings.s3_public_base_url.rstrip("/")
    return f"{base}/{key}"
