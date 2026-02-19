"""Fraud detection model."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier


class FraudModel:
    """Binary classifier for fraud detection using LightGBM."""

    def __init__(self, **params):
        defaults = {
            "objective": "binary",
            "metric": "auc",
            "is_unbalance": True,
            "max_depth": 8,
            "learning_rate": 0.05,
            "n_estimators": 500,
            "random_state": 42,
            "verbose": -1,
        }
        defaults.update(params)
        self.model = LGBMClassifier(**defaults)

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> FraudModel:
        self.model.fit(X, y)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X)

    def predict_fraud_score(self, X: pd.DataFrame) -> np.ndarray:
        return self.predict_proba(X)[:, 1]

    def save(self, path: str | Path) -> None:
        joblib.dump(self.model, path)

    @classmethod
    def load(cls, path: str | Path) -> FraudModel:
        instance = cls.__new__(cls)
        instance.model = joblib.load(path)
        return instance
