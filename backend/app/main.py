from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio.to_thread
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    admin,
    auth,
    health,
    kitchen,
    manager_catalog,
    me,
    menu,
    notifications,
    orders,
    payments,
    pickup,
    promotions,
    reference,
    reports,
    reviews,
    slots,
)
from app.config import get_settings
from app.errors import install_error_handlers
from app.logs import setup_logging
from app.metrics import install_http_metrics
from app.middleware import RequestIdMiddleware
from app.ws import routes as ws_routes

API_PREFIX = "/api/v1"


def db_threads() -> int:
    settings = get_settings()
    return settings.db_pool_size + settings.db_max_overflow


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # The default pool of 40 threads is larger than the DB pool: under a rush every thread can
    # end up waiting for a connection while the finished requests wait for a thread to close
    # their session, and everything stalls for the 30 s pool timeout (seen in the k6 test).
    anyio.to_thread.current_default_thread_limiter().total_tokens = db_threads()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(json=settings.app_env == "prod")
    app = FastAPI(
        title="Canteen Pre-order API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    install_http_metrics(app)
    for router in (
        health.router,
        auth.router,
        me.router,
        reference.router,
        menu.router,
        manager_catalog.router,
        admin.router,
        slots.router,
        orders.router,
        payments.router,
        kitchen.router,
        pickup.router,
        reviews.router,
        reports.router,
        promotions.router,
        notifications.router,
    ):
        app.include_router(router, prefix=API_PREFIX)
    app.include_router(ws_routes.router)
    return app


app = create_app()
