"""Точка входа FastAPI-приложения airsoft_kitfinder."""

from fastapi import FastAPI

from app.api import meta, products, public
from app.api.admin import auth as admin_auth
from app.api.admin import catalog as admin_catalog
from app.api.admin import kits as admin_kits
from app.api.admin import products as admin_products

app = FastAPI(title="airsoft_kitfinder", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.include_router(admin_auth.router)
app.include_router(admin_kits.router)
app.include_router(admin_catalog.router)
app.include_router(admin_products.router)
app.include_router(meta.router)
app.include_router(products.router)
app.include_router(public.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Проверка живости сервиса."""
    return {"status": "ok"}
