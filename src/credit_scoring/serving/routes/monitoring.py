"""Health and metrics API endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

from credit_scoring.serving.schemas import HealthResponse, MetricsResponse

router = APIRouter(tags=["monitoring"])


@router.get("/health", response_model=HealthResponse)
async def health_check(req: Request):
    """Check system health."""
    models_loaded = (
        req.app.state.scorer is not None
        and req.app.state.scorer.pd_model is not None
    )

    redis_ok = False
    if req.app.state.redis is not None:
        try:
            req.app.state.redis.ping()
            redis_ok = True
        except Exception:
            pass

    status = "healthy" if models_loaded else "unhealthy"
    if models_loaded and not redis_ok:
        status = "degraded"

    uptime = time.monotonic() - req.app.state.start_time

    return HealthResponse(
        status=status,
        models_loaded=models_loaded,
        redis_connected=redis_ok,
        uptime_seconds=round(uptime, 2),
        version="1.0.0",
    )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(req: Request):
    """Return model performance and operational metrics."""
    total = req.app.state.request_count
    total_latency = req.app.state.total_latency_ms
    errors = req.app.state.error_count

    return MetricsResponse(
        pd_model_auc=req.app.state.model_metrics.get("auc", 0.0),
        pd_model_ks=req.app.state.model_metrics.get("ks", 0.0),
        pd_model_gini=req.app.state.model_metrics.get("gini", 0.0),
        total_requests=total,
        avg_latency_ms=round(total_latency / max(total, 1), 2),
        error_rate=round(errors / max(total, 1), 4),
    )
