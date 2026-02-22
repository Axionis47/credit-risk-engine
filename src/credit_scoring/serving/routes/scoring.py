"""Scoring API endpoints."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Request

from credit_scoring.serving.schemas import (
    BatchScoringRequest,
    BatchScoringResponse,
    ScoringRequest,
    ScoringResponse,
)

router = APIRouter(tags=["scoring"])


@router.post("/score", response_model=ScoringResponse)
async def score_application(request: ScoringRequest, req: Request):
    """Score a single credit application."""
    start = time.monotonic()

    # Compute features
    features = req.app.state.feature_engineer.compute_single(request.model_dump())

    # Score through shadow mode (champion + challenger) or direct
    shadow_router = getattr(req.app.state, "shadow_router", None)
    if shadow_router is not None:
        result, _shadow = shadow_router.score(features, request.application_id)
    else:
        result = req.app.state.scorer.score_single(features)

    # Generate adverse action reasons if declined
    adverse_reasons = None
    if result["decision"] == "declined" and req.app.state.adverse_action is not None:
        reasons = req.app.state.adverse_action.generate_reasons(features)
        adverse_reasons = req.app.state.adverse_action.format_for_notice(reasons)

    latency_ms = (time.monotonic() - start) * 1000

    # Update metrics
    req.app.state.request_count += 1
    req.app.state.total_latency_ms += latency_ms

    return ScoringResponse(
        application_id=request.application_id,
        credit_score=int(result["credit_score"]),
        risk_tier=result["risk_tier"],
        probability_of_default=float(result["pd"]),
        loss_given_default=float(result["lgd"]),
        exposure_at_default=float(result["ead"]),
        expected_loss=float(result["expected_loss"]),
        fraud_score=float(result["fraud_score"]),
        fraud_flag=bool(result["fraud_flag"]),
        decision=result["decision"],
        adverse_action_reasons=adverse_reasons,
        scored_at=datetime.now(UTC),
        model_version="1.0.0",
    )


@router.post("/batch-score", response_model=BatchScoringResponse)
async def batch_score(request: BatchScoringRequest, req: Request):
    """Score multiple applications."""
    start = time.monotonic()
    results = []

    for app_request in request.applications:
        features = req.app.state.feature_engineer.compute_single(app_request.model_dump())
        result = req.app.state.scorer.score_single(features)

        adverse_reasons = None
        if result["decision"] == "declined" and req.app.state.adverse_action is not None:
            reasons = req.app.state.adverse_action.generate_reasons(features)
            adverse_reasons = req.app.state.adverse_action.format_for_notice(reasons)

        results.append(
            ScoringResponse(
                application_id=app_request.application_id,
                credit_score=int(result["credit_score"]),
                risk_tier=result["risk_tier"],
                probability_of_default=float(result["pd"]),
                loss_given_default=float(result["lgd"]),
                exposure_at_default=float(result["ead"]),
                expected_loss=float(result["expected_loss"]),
                fraud_score=float(result["fraud_score"]),
                fraud_flag=bool(result["fraud_flag"]),
                decision=result["decision"],
                adverse_action_reasons=adverse_reasons,
                scored_at=datetime.now(UTC),
                model_version="1.0.0",
            )
        )

    latency_ms = (time.monotonic() - start) * 1000

    return BatchScoringResponse(
        results=results,
        batch_id=str(uuid.uuid4()),
        total_processed=len(results),
        processing_time_ms=round(latency_ms, 2),
    )
