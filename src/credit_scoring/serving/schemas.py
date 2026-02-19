"""API request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ScoringRequest(BaseModel):
    application_id: str
    borrower_id: str
    age: int = Field(ge=18, le=100)
    annual_income: float = Field(gt=0)
    employment_length_years: float = Field(ge=0)
    employment_type: str
    home_ownership: str
    existing_credit_lines: int = Field(ge=0)
    total_credit_limit: float = Field(ge=0)
    current_credit_balance: float = Field(ge=0)
    credit_utilization_ratio: Optional[float] = None
    months_since_last_delinquency: Optional[int] = None
    number_of_delinquencies: int = Field(ge=0)
    debt_to_income_ratio: float = Field(ge=0)
    requested_loan_amount: float = Field(gt=0)
    loan_purpose: str
    state: str
    account_age_months: int = Field(ge=0)
    profile_completeness_score: float = Field(ge=0.0, le=1.0)
    device_type: str


class ScoringResponse(BaseModel):
    application_id: str
    credit_score: int = Field(ge=300, le=850)
    risk_tier: str
    probability_of_default: float
    loss_given_default: float
    exposure_at_default: float
    expected_loss: float
    fraud_score: float
    fraud_flag: bool
    decision: str
    adverse_action_reasons: Optional[list[dict]] = None
    scored_at: datetime
    model_version: str


class BatchScoringRequest(BaseModel):
    applications: list[ScoringRequest]


class BatchScoringResponse(BaseModel):
    results: list[ScoringResponse]
    batch_id: str
    total_processed: int
    processing_time_ms: float


class ExplanationResponse(BaseModel):
    application_id: str
    feature_contributions: list[dict]
    top_risk_factors: list[dict]
    top_protective_factors: list[dict]
    adverse_action_reasons: list[dict]


class HealthResponse(BaseModel):
    status: str
    models_loaded: bool
    redis_connected: bool
    uptime_seconds: float
    version: str


class MetricsResponse(BaseModel):
    pd_model_auc: float
    pd_model_ks: float
    pd_model_gini: float
    total_requests: int
    avg_latency_ms: float
    error_rate: float
