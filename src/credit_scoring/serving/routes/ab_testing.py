"""A/B testing and shadow mode API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["ab-testing"])


def _sanitize(obj):
    """Convert numpy types to native Python for JSON serialization."""
    import numpy as np

    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


@router.get("/shadow/report")
async def shadow_report(req: Request):
    """Get comparison report between champion and challenger models."""
    shadow_router = getattr(req.app.state, "shadow_router", None)
    if shadow_router is None:
        return {"status": "disabled", "message": "Shadow mode not active."}
    report = shadow_router.get_comparison_report()
    return JSONResponse(content=_sanitize(report))


@router.get("/shadow/recent")
async def shadow_recent(req: Request, limit: int = 20):
    """Get recent shadow comparison results."""
    shadow_router = getattr(req.app.state, "shadow_router", None)
    if shadow_router is None:
        return {"status": "disabled", "results": []}

    recent = shadow_router.shadow_log[-limit:]
    return {
        "status": "active",
        "count": len(recent),
        "results": [
            {
                "application_id": r.application_id,
                "champion_score": r.champion_score,
                "challenger_score": r.challenger_score,
                "champion_decision": r.champion_decision,
                "challenger_decision": r.challenger_decision,
                "agreement": r.agreement,
                "champion_latency_ms": r.champion_latency_ms,
                "challenger_latency_ms": r.challenger_latency_ms,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in recent
        ],
    }
