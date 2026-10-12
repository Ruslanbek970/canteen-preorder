from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth, health, manager_catalog, me, menu, reference
from app.config import get_settings
from app.errors import install_error_handlers

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Canteen Pre-order API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    for router in (
        health.router,
        auth.router,
        me.router,
        reference.router,
        menu.router,
        manager_catalog.router,
    ):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
