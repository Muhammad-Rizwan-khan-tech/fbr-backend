import os
from functools import lru_cache
from typing import List, Tuple

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-only-insecure-secret-key-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True)

    # --- General -----------------------------------------------------------------
    PROJECT_NAME: str = "FBR Invoice Cloud"
    PROJECT_VERSION: str = "1.1.0"
    API_V1_STR: str = "/api/v1"
    APP_ENV: str = "development"  # development | staging | production
    SERVICE_NAME: str = "fbr-invoice-api"
    LOG_LEVEL: str = "INFO"

    # --- Security ----------------------------------------------------------------
    SECRET_KEY: str = _DEV_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 20
    SUBMIT_RATE_LIMIT_PER_MINUTE: int = 60
    METRICS_TOKEN: str = ""  # if set, /metrics requires "Authorization: Bearer <token>"

    # --- Database ----------------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./fbr_invoice_cloud.db"
    DB_AUTO_CREATE: bool = True  # development convenience; staging/production use Alembic

    # --- Redis / queue -----------------------------------------------------------
    REDIS_URL: str = ""
    # "celery" (Redis broker + worker processes) or "inline" (no Redis; dev & tests)
    QUEUE_BACKEND: str = "inline"
    # inline backend only: "thread" runs jobs in a background thread, "manual" only queues (tests)
    QUEUE_INLINE_EXECUTION: str = "thread"
    JOB_STALE_SECONDS: int = 900  # PROCESSING jobs older than this are recovered by the sweeper
    QUEUED_REDISPATCH_SECONDS: int = 120  # QUEUED jobs never picked up are re-enqueued

    # --- FBR integration ---------------------------------------------------------
    FBR_ENVIRONMENT: str = "DEMO"  # default tenant environment: DEMO | SANDBOX | PRODUCTION
    FBR_PROVIDER: str = "MOCK"  # MOCK | SANDBOX | LICENSED_INTEGRATOR | PRODUCTION
    FBR_API_URL: str = ""
    FBR_API_KEY: str = ""
    FBR_CLIENT_ID: str = ""
    FBR_CLIENT_SECRET: str = ""
    FBR_HTTP_TIMEOUT_SECONDS: float = 15.0
    FBR_MAX_ATTEMPTS: int = 4
    FBR_RETRY_DELAYS_SECONDS: str = "300,900,1800"  # delay after attempt 1, 2, 3, ...
    FBR_STATUS_POLL_SECONDS: int = 60
    # mTLS Client Certificates (PRAL Gateway requirement)
    FBR_CLIENT_CERT_PATH: str = ""
    FBR_CLIENT_KEY_PATH: str = ""
    FBR_CA_CERT_PATH: str = ""
    FBR_CERT_PASSPHRASE: str = ""

    # --- Object storage ----------------------------------------------------------
    STORAGE_BACKEND: str = "local"  # local | s3
    LOCAL_STORAGE_PATH: str = "./storage_data"
    OBJECT_STORAGE_ENDPOINT: str = ""  # blank = AWS S3; set for MinIO / Cloudflare R2 / others
    OBJECT_STORAGE_REGION: str = "us-east-1"
    OBJECT_STORAGE_BUCKET: str = "fbr-invoice-documents"
    OBJECT_STORAGE_ACCESS_KEY: str = ""
    OBJECT_STORAGE_SECRET_KEY: str = ""
    SIGNED_URL_TTL_SECONDS: int = 300
    PUBLIC_API_BASE_URL: str = "http://localhost:8000"  # used to build local signed URLs

    # --- Disaster Recovery & Off-Site Replication -------------------------------
    BACKUP_OFFSITE_BUCKET: str = ""
    BACKUP_OFFSITE_STORAGE_CLASS: str = "GLACIER"
    BACKUP_ENCRYPTION_KEY: str = ""

    # --- Notifications -----------------------------------------------------------
    EMAIL_PROVIDER: str = "console"  # console | smtp | http | none
    EMAIL_API_KEY: str = ""
    EMAIL_API_URL: str = ""  # http provider endpoint
    EMAIL_FROM: str = "no-reply@fbr-invoice-cloud.example"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True

    @field_validator("APP_ENV")
    @classmethod
    def _validate_env(cls, v: str) -> str:
        v = v.lower()
        if v not in ("development", "staging", "production"):
            raise ValueError("APP_ENV must be development, staging or production")
        return v

    # ---- helpers ------------------------------------------------------------------
    @property
    def ENVIRONMENT(self) -> str:
        return self.APP_ENV

    @property
    def FBR_RETRY_MAX_ATTEMPTS(self) -> int:
        return self.FBR_MAX_ATTEMPTS

    @property
    def FBR_RETRY_INITIAL_DELAY_SECONDS(self) -> int:
        try:
            return int(self.FBR_RETRY_DELAYS_SECONDS.split(",")[0])
        except Exception:
            return 300

    @property
    def FBR_RETRY_BACKOFF_FACTOR(self) -> float:
        return 2.0

    @property
    def FBR_RETRY_MAX_DELAY_SECONDS(self) -> int:
        try:
            return int(self.FBR_RETRY_DELAYS_SECONDS.split(",")[-1])
        except Exception:
            return 1800

    @property
    def SMTP_USER(self) -> str:
        return self.SMTP_USERNAME

    @property
    def SMTP_FROM_EMAIL(self) -> str:
        return self.EMAIL_FROM

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def BACKEND_CORS_ORIGINS(self) -> List[str]:
        return self.cors_origins_list


    @property
    def retry_delays(self) -> Tuple[int, ...]:
        delays = tuple(int(x) for x in self.FBR_RETRY_DELAYS_SECONDS.split(",") if x.strip())
        return delays or (300,)

    def validate_for_runtime(self) -> None:
        """Fail fast on unsafe configuration outside development."""
        if self.APP_ENV == "development":
            return
        problems = []
        if self.SECRET_KEY == _DEV_SECRET or len(self.SECRET_KEY) < 32:
            problems.append("SECRET_KEY must be set to a strong value (>=32 chars)")
        if self.DB_AUTO_CREATE:
            problems.append("DB_AUTO_CREATE must be false (use `alembic upgrade head`)")
        if self.QUEUE_BACKEND != "celery":
            problems.append("QUEUE_BACKEND must be 'celery'")
        if self.QUEUE_BACKEND == "celery" and not self.REDIS_URL:
            problems.append("REDIS_URL is required")
        if self.STORAGE_BACKEND == "local" and self.is_production:
            problems.append("STORAGE_BACKEND=local is not allowed in production")
        if "*" in self.cors_origins_list:
            problems.append("CORS_ORIGINS must not contain '*'")
        if problems:
            raise RuntimeError("Unsafe configuration for APP_ENV=%s: %s" % (self.APP_ENV, "; ".join(problems)))


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
