"""Explanation API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from credit_scoring.serving.schemas import ExplanationResponse

router = APIRouter(tags=["explanation"])


@router.post("/score/{application_id}/explanation", response_model=ExplanationResponse)
async def get_explanation(application_id: str, req: Request):
    """Get SHAP explanation for a scoring request.

    Requires the same request body as /score to recompute features.
    """
    from credit_scoring.serving.schemas import ScoringRequest

    # For now, explanation requires re-sending the application data
    # A production system would cache scored features
    body = await req.json()
    body["application_id"] = application_id
    scoring_req = ScoringRequest(**body)

    if req.app.state.shap_explainer is None:
        raise HTTPException(status_code=503, detail="SHAP explainer not available")

    features = req.app.state.feature_engineer.compute_single(scoring_req.model_dump())
    explanation = req.app.state.shap_explainer.explain_local(features)

    adverse_reasons = []
    if req.app.state.adverse_action is not None:
        reasons = req.app.state.adverse_action.generate_reasons(features)
        adverse_reasons = req.app.state.adverse_action.format_for_notice(reasons)

    return ExplanationResponse(
        application_id=application_id,
        feature_contributions=explanation["feature_contributions"][:20],
        top_risk_factors=explanation["top_risk_factors"],
        top_protective_factors=explanation["top_protective_factors"],
        adverse_action_reasons=adverse_reasons,
    )
