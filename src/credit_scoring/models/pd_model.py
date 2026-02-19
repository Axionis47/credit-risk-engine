"""Probability of Default models: Logistic Regression, XGBoost, LightGBM."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier


class BasePDModel(ABC):
    """Abstract base class for Probability of Default models."""

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: np.ndarray) -> BasePDModel:
        ...

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        ...

    @abstractmethod
    def save(self, path: str | Path) -> None:
        ...

    @classmethod
    @abstractmethod
    def load(cls, path: str | Path) -> BasePDModel:
        ...

    def predict_pd(self, X: pd.DataFrame) -> np.ndarray:
        return self.predict_proba(X)[:, 1]


class LogisticPDModel(BasePDModel):
    """Logistic Regression baseline for PD estimation."""

    def __init__(self, C: float = 1.0, max_iter: int = 1000):
        self.pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                C=C, max_iter=max_iter, class_weight="balanced",
                solver="lbfgs", random_state=42,
            )),
        ])

    def fit(self, X, y):
        self.pipeline.fit(X, y)
        return self

    def predict_proba(self, X):
        return self.pipeline.predict_proba(X)

    def save(self, path):
        joblib.dump(self.pipeline, path)

    @classmethod
    def load(cls, path):
        instance = cls.__new__(cls)
        instance.pipeline = joblib.load(path)
        return instance


class XGBoostPDModel(BasePDModel):
    """XGBoost model for PD estimation."""

    def __init__(self, **params):
        defaults = {
            "objective": "binary:logistic",
            "eval_metric": "auc",
            "n_estimators": 300,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "verbosity": 0,
        }
        defaults.update(params)
        self.model = XGBClassifier(**defaults)

    def fit(self, X, y):
        self.model.fit(X, y)
        return self

    def predict_proba(self, X):
        return self.model.predict_proba(X)

    def save(self, path):
        joblib.dump(self.model, path)

    @classmethod
    def load(cls, path):
        instance = cls.__new__(cls)
        instance.model = joblib.load(path)
        return instance


class LightGBMPDModel(BasePDModel):
    """LightGBM model for PD estimation."""

    def __init__(self, **params):
        defaults = {
            "objective": "binary",
            "metric": "auc",
            "n_estimators": 300,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "is_unbalance": True,
            "random_state": 42,
            "verbose": -1,
        }
        defaults.update(params)
        self.model = LGBMClassifier(**defaults)

    def fit(self, X, y):
        self.model.fit(X, y)
        return self

    def predict_proba(self, X):
        return self.model.predict_proba(X)

    def save(self, path):
        joblib.dump(self.model, path)

    @classmethod
    def load(cls, path):
        instance = cls.__new__(cls)
        instance.model = joblib.load(path)
        return instance


def create_pd_model(model_type: str, **params) -> BasePDModel:
    """Factory function for PD models."""
    models = {
        "logistic": LogisticPDModel,
        "xgboost": XGBoostPDModel,
        "lightgbm": LightGBMPDModel,
    }
    if model_type not in models:
        raise ValueError(f"Unknown model type: {model_type}. Choose from {list(models)}")
    return models[model_type](**params)
