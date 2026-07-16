"""Точка входа FastAPI-приложения airsoft_kitfinder."""

from fastapi import FastAPI

app = FastAPI(title="airsoft_kitfinder", docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Проверка живости сервиса."""
    return {"status": "ok"}
