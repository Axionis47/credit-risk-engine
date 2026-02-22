"""Exposure at Default model."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor


class EADModel:
    """Hybrid EAD model.

    EAD = drawn_amount + CCF * (limit - drawn_amount)

    The Credit Conversion Factor (CCF) is predicted by an ML model when available,
    with a regulatory fallback of 0.75.
    """

    def __init__(self, regulatory_ccf: float = 0.75):
        self.regulatory_ccf = regulatory_ccf
        self.ccf_model = XGBRegressor(
            max_depth=3,
            n_estimators=100,
            learning_rate=0.05,
            random_state=42,
            verbosity=0,
        )
        self.is_fitted = False

    def fit(self, X: pd.DataFrame, y_ccf: np.ndarray) -> EADModel:
        """Train CCF model.

        y_ccf = (ead_actual - drawn) / (limit - drawn) for cases where limit > drawn.
        """
        valid = np.isfinite(y_ccf) & (y_ccf >= 0) & (y_ccf <= 1)
        if valid.sum() > 10:
            self.ccf_model.fit(X[valid], y_ccf[valid])
            self.is_fitted = True
        return self

    def predict(self, X: pd.DataFrame, drawn: np.ndarray, limit: np.ndarray) -> np.ndarray:
        """Predict EAD for each borrower."""
        if self.is_fitted:
            ccf = np.clip(self.ccf_model.predict(X), 0.0, 1.0)
        else:
            ccf = np.full(len(X), self.regulatory_ccf)

        undrawn = np.maximum(limit - drawn, 0)
        ead = drawn + ccf * undrawn
        return np.clip(ead, drawn, limit)

    def save(self, path: str | Path) -> None:
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str | Path) -> EADModel:
        return joblib.load(path)
