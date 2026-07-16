"""Точка входа FastAPI-приложения airsoft_kitfinder."""

from fastapi import FastAPI

from app.api.admin import auth as admin_auth

app = FastAPI(title="airsoft_kitfinder", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.include_router(admin_auth.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Проверка живости сервиса."""
    return {"status": "ok"}
