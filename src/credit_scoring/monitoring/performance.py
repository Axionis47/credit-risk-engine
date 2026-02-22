"""Model performance tracking over time."""

from __future__ import annotations

import numpy as np
import pandas as pd

from credit_scoring.models.evaluation import ModelEvaluator


class PerformanceMonitor:
    """Track model performance metrics over time."""

    def __init__(self):
        self.evaluator = ModelEvaluator()
        self.history: list[dict] = []

    def record_batch(self, y_true: np.ndarray, y_prob: np.ndarray, timestamp: str):
        metrics = self.evaluator.evaluate_pd(y_true, y_prob)
        metrics["timestamp"] = timestamp
        self.history.append(metrics)

    def check_degradation(self, metric: str = "auc_roc", threshold: float = 0.05) -> bool:
        """Check if metric has degraded beyond threshold vs initial."""
        if len(self.history) < 2:
            return False
        initial = self.history[0].get(metric, 0)
        current = self.history[-1].get(metric, 0)
        return (initial - current) > threshold

    def get_metrics_timeseries(self) -> pd.DataFrame:
        if not self.history:
            return pd.DataFrame()
        return pd.DataFrame(self.history)
