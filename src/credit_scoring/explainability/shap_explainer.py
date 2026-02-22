"""SHAP-based model explanations for credit scoring."""

from __future__ import annotations

import numpy as np
import pandas as pd
import shap


class SHAPExplainer:
    """Compute global and local SHAP explanations."""

    def __init__(self, model, X_background: pd.DataFrame, max_background: int = 500):
        background = X_background.sample(min(max_background, len(X_background)), random_state=42)

        if hasattr(model, "model") and hasattr(model.model, "get_booster"):
            # XGBoost
            self.explainer = shap.TreeExplainer(model.model)
        elif hasattr(model, "model") and hasattr(model.model, "booster_"):
            # LightGBM
            self.explainer = shap.TreeExplainer(model.model)
        elif hasattr(model, "pipeline"):
            # Logistic Regression pipeline
            self.explainer = shap.LinearExplainer(
                model.pipeline.named_steps["clf"],
                model.pipeline.named_steps["scaler"].transform(background),
            )
            self._scaler = model.pipeline.named_steps["scaler"]
        else:
            self.explainer = shap.KernelExplainer(
                model.predict_proba if hasattr(model, "predict_proba") else model.predict,
                background,
            )

        self._background = background
        self._is_linear = hasattr(self, "_scaler")

    def explain_global(self, X: pd.DataFrame) -> dict:
        """Global feature importance from SHAP values."""
        shap_values = self.get_shap_values(X)
        feature_names = X.columns.tolist()

        mean_abs = np.abs(shap_values).mean(axis=0)
        importance = sorted(
            zip(feature_names, mean_abs),
            key=lambda x: x[1],
            reverse=True,
        )

        return {
            "feature_importance": [{"feature": name, "importance": float(imp)} for name, imp in importance],
        }

    def explain_local(self, X_single: pd.DataFrame) -> dict:
        """Explain a single prediction."""
        shap_values = self.get_shap_values(X_single)
        if shap_values.ndim > 1:
            sv = shap_values[0]
        else:
            sv = shap_values

        feature_names = X_single.columns.tolist()
        feature_values = X_single.iloc[0].values

        contributions = []
        for name, value, shap_val in zip(feature_names, feature_values, sv):
            contributions.append(
                {
                    "feature": name,
                    "value": float(value),
                    "shap_value": float(shap_val),
                    "direction": "increases_risk" if shap_val > 0 else "decreases_risk",
                }
            )

        contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

        return {
            "feature_contributions": contributions,
            "top_risk_factors": [c for c in contributions if c["direction"] == "increases_risk"][:5],
            "top_protective_factors": [c for c in contributions if c["direction"] == "decreases_risk"][:5],
        }

    def get_shap_values(self, X: pd.DataFrame) -> np.ndarray:
        """Return raw SHAP values."""
        if self._is_linear:
            X_scaled = self._scaler.transform(X)
            shap_values = self.explainer.shap_values(X_scaled)
        else:
            shap_values = self.explainer.shap_values(X)

        if isinstance(shap_values, list):
            return shap_values[1]  # Class 1 (default)
        return shap_values
