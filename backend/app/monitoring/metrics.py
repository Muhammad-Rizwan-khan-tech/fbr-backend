"""Provider-neutral instrumentation (Prometheus text exposition format).

Metrics are defined once here and incremented from the API and worker code.
"""
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

registry = CollectorRegistry()

HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"], registry=registry)
HTTP_LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "route"],
                         buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10), registry=registry)
HTTP_ERRORS = Counter("http_errors_total", "HTTP 5xx responses", ["route"], registry=registry)

FBR_SUBMISSIONS = Counter("fbr_submissions_total", "FBR submission attempt outcomes",
                          ["environment", "provider", "outcome"], registry=registry)
FBR_LATENCY = Histogram("fbr_submission_duration_seconds", "FBR adapter call latency", ["environment", "provider"],
                        buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30), registry=registry)
FBR_REJECTIONS = Counter("fbr_rejections_total", "FBR rejections", ["environment", "provider"], registry=registry)

JOB_RESULTS = Counter("worker_jobs_total", "Worker job outcomes", ["job_type", "outcome"], registry=registry)
JOB_FAILURES = Counter("worker_job_failures_total", "Worker job failures", ["job_type"], registry=registry)

PDF_DURATION = Histogram("pdf_generation_duration_seconds", "PDF generation time", ["document_type"],
                         buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5), registry=registry)
STORAGE_FAILURES = Counter("storage_failures_total", "Storage operation failures", ["operation"], registry=registry)

QUEUE_DEPTH = Gauge("queue_depth", "Messages waiting in a queue", ["queue"], registry=registry)
COMPONENT_UP = Gauge("component_up", "1 if component healthy", ["component"], registry=registry)


def render_metrics() -> bytes:
    return generate_latest(registry)


METRICS_CONTENT_TYPE = CONTENT_TYPE_LATEST


def record_http_request(method: str, route: str, status: int, duration: float) -> None:
    try:
        clean_route = route.split("?")[0]
        HTTP_REQUESTS.labels(method=method, route=clean_route, status=str(status)).inc()
        HTTP_LATENCY.labels(method=method, route=clean_route).observe(duration)
        if status >= 500:
            HTTP_ERRORS.labels(route=clean_route).inc()
    except Exception:
        pass


def record_fbr_submission(environment: str, outcome: str, provider: str = "MOCK") -> None:
    try:
        FBR_SUBMISSIONS.labels(environment=environment, provider=provider, outcome=outcome).inc()
        if outcome in ("rejected", "invalid"):
            FBR_REJECTIONS.labels(environment=environment, provider=provider).inc()
    except Exception:
        pass


def record_fbr_latency(environment: str, duration: float, provider: str = "MOCK") -> None:
    try:
        FBR_LATENCY.labels(environment=environment, provider=provider).observe(duration)
    except Exception:
        pass


def record_worker_job(job_type: str, outcome: str, duration: float = 0.0) -> None:
    try:
        JOB_RESULTS.labels(job_type=job_type, outcome=outcome).inc()
        if outcome in ("failed", "error"):
            JOB_FAILURES.labels(job_type=job_type).inc()
    except Exception:
        pass


def record_pdf_generation(duration: float, document_type: str = "INVOICE_PDF") -> None:
    try:
        PDF_DURATION.labels(document_type=document_type).observe(duration)
    except Exception:
        pass


class MetricsCollector:
    @staticmethod
    def generate_prometheus_exposition() -> str:
        return render_metrics().decode("utf-8")


metrics_collector = MetricsCollector()

