"""Админские эндпоинты аутентификации: login / logout / me."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.auth import (
    clear_session_cookie,
    issue_session_cookie,
    require_admin,
    verify_password,
)
from app.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
async def login(body: LoginRequest, response: Response) -> dict[str, str]:
    """Проверяет пароль админа и выдаёт сессионную cookie."""
    if not verify_password(body.password, settings.admin_password_hash):
        await asyncio.sleep(settings.login_fail_delay_seconds)  # анти-брутфорс
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный пароль")
    issue_session_cookie(response)
    return {"status": "ok"}


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Сбрасывает сессионную cookie."""
    clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/me")
async def me(_: None = Depends(require_admin)) -> dict[str, bool]:
    """Возвращает признак авторизованного админа (для гарда роутов на фронте)."""
    return {"admin": True}
