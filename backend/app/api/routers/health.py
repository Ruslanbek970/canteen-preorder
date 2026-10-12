from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db import check_db
from app.redis_client import check_redis

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/health/ready")
def ready() -> JSONResponse:
    """Readiness: database and Redis are reachable."""
    checks = {"db": check_db(), "redis": check_redis()}
    ok = all(checks.values())
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "unavailable", "checks": checks},
    )
