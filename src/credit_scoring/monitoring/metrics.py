"""Prometheus metrics for credit scoring API."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, generate_latest

SCORING_REQUESTS = Counter(
    "credit_scoring_requests_total",
    "Total scoring requests",
    ["endpoint", "status"],
)

SCORING_LATENCY = Histogram(
    "credit_scoring_latency_seconds",
    "Scoring request latency",
    ["endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

MODEL_AUC = Gauge(
    "credit_scoring_model_auc",
    "Current model AUC-ROC",
    ["model_type"],
)

DATA_DRIFT_PSI = Gauge(
    "credit_scoring_data_drift_psi",
    "Current data drift PSI",
    ["feature"],
)

FAIRNESS_DISPARITY = Gauge(
    "credit_scoring_fairness_disparity",
    "Current fairness disparity metric",
    ["metric", "group"],
)


def get_prometheus_metrics() -> bytes:
    return generate_latest()
