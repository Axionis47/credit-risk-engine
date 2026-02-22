"""Fairness metrics for credit scoring models."""

from __future__ import annotations

import numpy as np


class FairnessMetrics:
    """Compute fairness metrics across protected groups."""

    def __init__(self, protected_attribute: str, favorable_outcome: int = 0):
        self.protected_attribute = protected_attribute
        self.favorable_outcome = favorable_outcome

    def demographic_parity(self, y_pred: np.ndarray, groups: np.ndarray) -> dict:
        """Approval rates should be equal across groups."""
        favorable = y_pred == self.favorable_outcome
        unique_groups = np.unique(groups)

        approval_rates = {}
        for g in unique_groups:
            mask = groups == g
            approval_rates[str(g)] = float(favorable[mask].mean())

        rates = list(approval_rates.values())
        max_disparity = max(rates) - min(rates) if rates else 0.0

        return {
            "approval_rates": approval_rates,
            "max_disparity": float(max_disparity),
            "passed": max_disparity < 0.10,
        }

    def equalized_odds(self, y_true: np.ndarray, y_pred: np.ndarray, groups: np.ndarray) -> dict:
        """TPR and FPR should be equal across groups."""
        unique_groups = np.unique(groups)
        tpr_by_group = {}
        fpr_by_group = {}

        for g in unique_groups:
            mask = groups == g
            y_t = y_true[mask]
            y_p = y_pred[mask]

            pos = y_t == 1
            neg = y_t == 0

            tpr = float(y_p[pos].mean()) if pos.sum() > 0 else 0.0
            fpr = float(y_p[neg].mean()) if neg.sum() > 0 else 0.0

            tpr_by_group[str(g)] = tpr
            fpr_by_group[str(g)] = fpr

        tpr_vals = list(tpr_by_group.values())
        fpr_vals = list(fpr_by_group.values())

        return {
            "tpr_by_group": tpr_by_group,
            "fpr_by_group": fpr_by_group,
            "tpr_disparity": float(max(tpr_vals) - min(tpr_vals)) if tpr_vals else 0.0,
            "fpr_disparity": float(max(fpr_vals) - min(fpr_vals)) if fpr_vals else 0.0,
            "passed": (max(tpr_vals) - min(tpr_vals) < 0.10) if tpr_vals else True,
        }

    def disparate_impact_ratio(self, y_pred: np.ndarray, groups: np.ndarray, privileged_group: str) -> dict:
        """4/5 rule: approval ratio between groups must be >= 0.80."""
        favorable = y_pred == self.favorable_outcome
        unique_groups = np.unique(groups)

        priv_mask = groups == privileged_group
        priv_rate = float(favorable[priv_mask].mean()) if priv_mask.sum() > 0 else 1.0

        ratios = {}
        for g in unique_groups:
            if str(g) == privileged_group:
                continue
            mask = groups == g
            rate = float(favorable[mask].mean()) if mask.sum() > 0 else 0.0
            ratio = rate / priv_rate if priv_rate > 0 else 0.0
            ratios[f"{g}_vs_{privileged_group}"] = float(ratio)

        min_ratio = min(ratios.values()) if ratios else 1.0

        return {
            "ratios": ratios,
            "min_ratio": float(min_ratio),
            "passed": min_ratio >= 0.80,
        }

    def compute_all(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_prob: np.ndarray,
        groups: np.ndarray,
        privileged_group: str,
    ) -> dict:
        """Run all fairness checks."""
        return {
            "demographic_parity": self.demographic_parity(y_pred, groups),
            "equalized_odds": self.equalized_odds(y_true, y_pred, groups),
            "disparate_impact": self.disparate_impact_ratio(y_pred, groups, privileged_group),
        }


class BiasMonitor:
    """Track fairness metrics over time."""

    def __init__(self):
        self.history: list[dict] = []

    def record_metrics(self, metrics: dict, timestamp: str):
        self.history.append({"timestamp": timestamp, **metrics})

    def check_degradation(self, window: int = 30) -> list[str]:
        """Check if any fairness metric has degraded."""
        warnings = []
        if len(self.history) < 2:
            return warnings

        recent = self.history[-1]
        if "demographic_parity" in recent:
            if not recent["demographic_parity"].get("passed", True):
                warnings.append("Demographic parity check failed")
        if "disparate_impact" in recent:
            if not recent["disparate_impact"].get("passed", True):
                warnings.append("Disparate impact ratio below 0.80 threshold")

        return warnings
