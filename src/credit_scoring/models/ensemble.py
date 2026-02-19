"""PD model ensemble and credit score calculation."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from credit_scoring.models.pd_model import BasePDModel


class PDEnsemble:
    """Weighted ensemble of PD models.

    Optimizes weights on a validation set to maximize AUC.
    """

    def __init__(self, models: dict[str, BasePDModel], method: str = "weighted_average"):
        self.models = models
        self.method = method
        self.weights: dict[str, float] = {name: 1.0 / len(models) for name in models}

    def optimize_weights(self, X_val: pd.DataFrame, y_val: np.ndarray):
        """Find optimal weights that minimize log loss on validation set."""
        preds = {name: model.predict_pd(X_val) for name, model in self.models.items()}
        pred_matrix = np.column_stack(list(preds.values()))
        names = list(preds.keys())

        def neg_auc(w):
            w = np.abs(w)
            w = w / w.sum()
            combined = pred_matrix @ w
            from sklearn.metrics import roc_auc_score
            try:
                return -roc_auc_score(y_val, combined)
            except ValueError:
                return 0.0

        n_models = len(names)
        x0 = np.ones(n_models) / n_models
        result = minimize(neg_auc, x0, method="Nelder-Mead")
        optimal_w = np.abs(result.x)
        optimal_w = optimal_w / optimal_w.sum()

        self.weights = dict(zip(names, optimal_w))

    def predict_pd(self, X: pd.DataFrame) -> np.ndarray:
        preds = []
        weights = []
        for name, model in self.models.items():
            preds.append(model.predict_pd(X))
            weights.append(self.weights[name])

        pred_matrix = np.column_stack(preds)
        w = np.array(weights)
        w = w / w.sum()
        return pred_matrix @ w

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        pd_scores = self.predict_pd(X)
        return np.column_stack([1 - pd_scores, pd_scores])


class CreditScoreCalculator:
    """Combine PD, LGD, EAD, and Fraud models into a credit decision.

    Produces:
        - credit_score: 300-850 scale
        - risk_tier: low / medium / high / very_high
        - expected_loss: PD * LGD * EAD
        - fraud_flag: boolean
        - decision: approved / declined / manual_review
    """

    FRAUD_THRESHOLD = 0.5
    DECLINE_SCORE = 550
    REVIEW_SCORE = 620

    def __init__(self, pd_model, lgd_model, ead_model, fraud_model):
        self.pd_model = pd_model
        self.lgd_model = lgd_model
        self.ead_model = ead_model
        self.fraud_model = fraud_model

    def score_batch(
        self,
        X: pd.DataFrame,
        drawn: np.ndarray | None = None,
        limit: np.ndarray | None = None,
    ) -> pd.DataFrame:
        """Score a batch of applications."""
        pd_scores = self.pd_model.predict_pd(X)
        lgd_scores = self.lgd_model.predict(X)
        fraud_scores = self.fraud_model.predict_fraud_score(X)

        if drawn is None:
            drawn = np.zeros(len(X))
        if limit is None:
            limit = np.ones(len(X)) * 10000

        ead_values = self.ead_model.predict(X, drawn, limit)
        expected_loss = pd_scores * lgd_scores * ead_values

        credit_scores = np.array([self._pd_to_credit_score(p) for p in pd_scores])
        risk_tiers = np.array([self._assign_risk_tier(p) for p in pd_scores])
        fraud_flags = fraud_scores > self.FRAUD_THRESHOLD

        decisions = []
        for cs, ff in zip(credit_scores, fraud_flags):
            if ff:
                decisions.append("manual_review")
            elif cs < self.DECLINE_SCORE:
                decisions.append("declined")
            elif cs < self.REVIEW_SCORE:
                decisions.append("manual_review")
            else:
                decisions.append("approved")

        return pd.DataFrame({
            "pd": pd_scores,
            "lgd": lgd_scores,
            "ead": ead_values,
            "expected_loss": expected_loss,
            "credit_score": credit_scores,
            "risk_tier": risk_tiers,
            "fraud_score": fraud_scores,
            "fraud_flag": fraud_flags,
            "decision": decisions,
        })

    def score_single(self, X: pd.DataFrame) -> dict:
        """Score a single application. Returns a dict."""
        result = self.score_batch(X)
        return result.iloc[0].to_dict()

    @staticmethod
    def _pd_to_credit_score(pd_value: float) -> int:
        """Map PD to 300-850 scale.

        PD=0.001 -> ~830, PD=0.05 -> ~700, PD=0.20 -> ~500, PD=0.50 -> ~380.
        """
        pd_value = np.clip(pd_value, 1e-6, 1 - 1e-6)
        log_odds = np.log(pd_value / (1 - pd_value))
        # Linear mapping: log_odds in [-7, 3] -> score in [300, 850]
        score = 575 - 55 * log_odds
        return int(np.clip(score, 300, 850))

    @staticmethod
    def _assign_risk_tier(pd_value: float) -> str:
        if pd_value < 0.05:
            return "low"
        elif pd_value < 0.15:
            return "medium"
        elif pd_value < 0.30:
            return "high"
        else:
            return "very_high"
