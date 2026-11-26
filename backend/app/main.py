import time
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse

from backend.app.core.config import settings
from backend.app.core.context import execution_context
from backend.app.core.database import Base, engine, SessionLocal, ensure_schema_columns
from backend.app.core.errors import AppError
from backend.app.core.logging import setup_logging
from backend.app.monitoring.metrics import metrics_collector, record_http_request
from backend.app.api.api_v1 import api_router
from backend.app.api.routes.health import router as health_router, healthcheck
from backend.app.core.middleware import SecurityHeadersMiddleware
from backend.app.seed.seed_data import seed_database
import backend.app.models  # noqa: F401 - register all ORM models

# Configure production JSON structured logging
setup_logging(level=settings.LOG_LEVEL)
ensure_schema_columns(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runtime safety check (enforces strong secrets outside dev)
    settings.validate_for_runtime()

    # Startup: Ensure database schema is created and seeded with reference data
    ensure_schema_columns(engine)
    try:
        db = SessionLocal()
        seed_database(db)
        db.close()
    except Exception as e:
        print(f"Warning during initial DB seeding: {e}")
    yield

    # Shutdown logic (if any)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="Multi-tenant Web SaaS for Digital Tax Invoicing and Pakistan FBR Integration",
    lifespan=lifespan,
)

# Security Headers & CORS Middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_and_metrics_middleware(request: Request, call_next):
    """Injects request and correlation IDs into contextvars and records Prometheus metrics."""
    req_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:10]}"
    corr_id = request.headers.get("X-Correlation-ID") or req_id

    execution_context.request_id.set(req_id)
    execution_context.correlation_id.set(corr_id)

    start_time = time.time()
    try:
        response: Response = await call_next(request)
        duration = time.time() - start_time
        record_http_request(request.method, request.url.path, response.status_code, duration)
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Correlation-ID"] = corr_id
        return response
    except Exception as exc:
        duration = time.time() - start_time
        record_http_request(request.method, request.url.path, 500, duration)
        raise exc


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """Standardized JSON error envelope."""
    corr_id = execution_context.correlation_id.get() or "unknown"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "correlation_id": corr_id,
            },
            "detail": exc.message,  # Legacy backwards-compatibility
        },
    )


# Include Master API V1
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(health_router)


@app.get("/health", tags=["Health"])
def root_health():
    """Deep healthcheck endpoint at root level."""
    db = SessionLocal()
    try:
        return healthcheck(db)
    finally:
        db.close()


@app.get("/metrics", tags=["Metrics"])
def get_metrics(request: Request):
    """Prometheus exposition metrics with optional token protection."""
    if settings.METRICS_TOKEN:
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {settings.METRICS_TOKEN}":
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid metrics token")
    content = metrics_collector.generate_prometheus_exposition()
    return Response(content=content, media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Welcome to FBR Invoice Cloud API",
        "docs_url": "/docs",
        "developer_portal": "/developer/portal",
        "api_v1": settings.API_V1_STR,
    }


@app.get("/developer/portal", response_class=HTMLResponse, tags=["Developer Portal"])
@app.get("/docs/developer-guide", response_class=HTMLResponse, tags=["Developer Portal"])
@app.get("/api/v1/developer/portal", response_class=HTMLResponse, tags=["Developer Portal"])
def get_developer_portal():
    """Serves the interactive ERP Integration and Developer Portal."""
    template_path = Path(__file__).resolve().parent / "templates" / "developer_portal.html"
    if template_path.is_file():
        return HTMLResponse(content=template_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>FBR Developer Portal</h1>", status_code=200)

