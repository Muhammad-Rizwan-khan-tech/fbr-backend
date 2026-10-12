from fastapi import APIRouter, Response
from backend.app.monitoring.metrics import metrics_collector

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def get_prometheus_metrics():
    """Exposes application and compliance metrics in standard Prometheus exposition format."""
    exposition = metrics_collector.generate_prometheus_exposition()
    return Response(content=exposition, media_type="text/plain; version=0.0.4; charset=utf-8")
