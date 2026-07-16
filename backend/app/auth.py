"""Аутентификация админа: bcrypt-пароль + подписанная cookie-сессия."""

import bcrypt
from fastapi import HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from app.config import settings

COOKIE_NAME = "kf_admin"
COOKIE_MAX_AGE = 14 * 24 * 3600  # 14 дней в секундах
_SESSION_VALUE = "admin"


def _signer() -> TimestampSigner:
    return TimestampSigner(settings.secret_key)


def hash_password(password: str) -> str:
    """Возвращает bcrypt-хеш пароля (для генерации ADMIN_PASSWORD_HASH)."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет пароль против bcrypt-хеша."""
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def issue_session_cookie(response: Response) -> None:
    """Ставит подписанную httpOnly-cookie админской сессии."""
    token = _signer().sign(_SESSION_VALUE).decode()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )


def clear_session_cookie(response: Response) -> None:
    """Удаляет cookie админской сессии."""
    response.delete_cookie(COOKIE_NAME)


def require_admin(request: Request) -> None:
    """FastAPI-зависимость: пускает только при валидной сессионной cookie."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    try:
        _signer().unsign(token, max_age=COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Сессия недействительна"
        ) from exc
