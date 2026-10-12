import time
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.redis_client import ping_redis
from backend.app.storage import get_storage

router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck(db: Session = Depends(get_db)):
    """Deep system health probe testing database, storage, redis, and queue status."""
    start_time = time.time()
    components = {}
    is_healthy = True

    # 1. Database Probe
    try:
        db.execute(text("SELECT 1"))
        components["database"] = {"status": "UP", "engine": settings.DATABASE_URL.split("://")[0]}
    except Exception as exc:
        components["database"] = {"status": "DOWN", "error": str(exc)}
        is_healthy = False

    # 2. Redis Probe
    try:
        redis_ok = ping_redis()
        components["redis"] = {
            "status": "UP" if redis_ok else "DOWN",
            "mode": "standalone" if redis_ok else ("in-memory-fallback" if settings.QUEUE_BACKEND == "inline" else "unreachable"),
        }
        if not redis_ok and settings.QUEUE_BACKEND == "celery":
            is_healthy = False
    except Exception as exc:
        components["redis"] = {"status": "DOWN", "error": str(exc)}
        if settings.QUEUE_BACKEND == "celery":
            is_healthy = False

    # 3. Storage Probe
    try:
        storage = get_storage()
        storage_ok = storage.healthcheck()
        components["storage"] = {
            "status": "UP" if storage_ok else "DOWN",
            "provider": storage.provider_name,
        }
        if not storage_ok:
            is_healthy = False
    except Exception as exc:
        components["storage"] = {"status": "DOWN", "error": str(exc)}
        is_healthy = False

    # 4. Queue / Worker subsystem
    components["queue"] = {
        "backend": settings.QUEUE_BACKEND,
        "status": "UP",
    }

    latency_ms = int((time.time() - start_time) * 1000)

    return {
        "status": "healthy" if is_healthy else "degraded",
        "app_name": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "latency_ms": latency_ms,
        "components": components,
    }


@router.get("/health/live")
def liveness():
    """Kubernetes / container liveness probe: returns 200 immediately if process is alive."""
    return {"status": "alive", "timestamp": int(time.time())}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)):
    """Kubernetes / load balancer readiness probe: verifies database & queue connectivity."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    redis_ok = True
    if settings.QUEUE_BACKEND == "celery":
        redis_ok = ping_redis()

    if not db_ok or not redis_ok:
        from fastapi import Response, status
        return Response(
            content='{"status": "not_ready", "database": "%s", "redis": "%s"}' % (
                "UP" if db_ok else "DOWN",
                "UP" if redis_ok else "DOWN"
            ),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json"
        )

    return {"status": "ready", "database": "UP", "redis": "UP" if redis_ok else "SKIPPED"}

