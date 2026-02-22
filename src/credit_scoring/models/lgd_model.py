"""Loss Given Default models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from xgboost import XGBRegressor


class BaseLGDModel(ABC):
    """Abstract base for LGD models. Predicts values in [0, 1]."""

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: np.ndarray) -> BaseLGDModel: ...

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray: ...

    def save(self, path: str | Path) -> None:
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str | Path) -> BaseLGDModel:
        return joblib.load(path)


class TwoStageLGDModel(BaseLGDModel):
    """Two-stage LGD model.

    Stage 1: Classify zero-loss vs positive-loss (LogisticRegression).
    Stage 2: Predict loss severity given positive-loss (XGBRegressor).

    Final prediction: P(positive_loss) * E[loss | positive_loss], clipped to [0, 1].
    """

    def __init__(self):
        self.stage1 = LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=42,
        )
        self.stage2 = XGBRegressor(
            objective="reg:squarederror",
            max_depth=4,
            learning_rate=0.05,
            n_estimators=200,
            random_state=42,
            verbosity=0,
        )
        self._scaler = None

    def fit(self, X, y):
        from sklearn.preprocessing import StandardScaler

        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        # Stage 1: zero-loss vs positive-loss
        y_binary = (y > 0).astype(int)
        self.stage1.fit(X_scaled, y_binary)

        # Stage 2: loss severity for positive-loss cases
        pos_mask = y > 0
        if pos_mask.sum() > 10:
            self.stage2.fit(X_scaled[pos_mask], y[pos_mask])

        return self

    def predict(self, X):
        X_scaled = self._scaler.transform(X)
        prob_positive = self.stage1.predict_proba(X_scaled)[:, 1]
        severity = self.stage2.predict(X_scaled)
        lgd = prob_positive * severity
        return np.clip(lgd, 0.0, 1.0)


class GradientBoostingLGDModel(BaseLGDModel):
    """Direct gradient boosting regression for LGD."""

    def __init__(self, **params):
        defaults = {
            "objective": "reg:squarederror",
            "max_depth": 4,
            "learning_rate": 0.05,
            "n_estimators": 200,
            "random_state": 42,
            "verbosity": 0,
        }
        defaults.update(params)
        self.model = XGBRegressor(**defaults)

    def fit(self, X, y):
        self.model.fit(X, y)
        return self

    def predict(self, X):
        return np.clip(self.model.predict(X), 0.0, 1.0)
