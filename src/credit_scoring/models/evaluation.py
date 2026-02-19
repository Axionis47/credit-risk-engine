"""Model evaluation metrics for credit scoring."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    brier_score_loss,
    classification_report,
    confusion_matrix,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)


class ModelEvaluator:
    """Compute evaluation metrics for PD, LGD, and EAD models."""

    def evaluate_pd(self, y_true: np.ndarray, y_prob: np.ndarray) -> dict:
        """Full PD model evaluation."""
        auc = roc_auc_score(y_true, y_prob)
        gini = 2 * auc - 1
        ks = self.compute_ks_statistic(y_true, y_prob)
        ll = log_loss(y_true, y_prob)
        brier = brier_score_loss(y_true, y_prob)

        # Optimal threshold via Youden's J
        from sklearn.metrics import roc_curve
        fpr, tpr, thresholds = roc_curve(y_true, y_prob)
        j_scores = tpr - fpr
        best_idx = np.argmax(j_scores)
        optimal_threshold = thresholds[best_idx]

        y_pred = (y_prob >= optimal_threshold).astype(int)
        report = classification_report(y_true, y_pred, output_dict=True)
        cm = confusion_matrix(y_true, y_pred)

        decile_table = self.compute_decile_table(y_true, y_prob)

        return {
            "auc_roc": float(auc),
            "gini": float(gini),
            "ks_statistic": float(ks),
            "log_loss": float(ll),
            "brier_score": float(brier),
            "optimal_threshold": float(optimal_threshold),
            "classification_report": report,
            "confusion_matrix": cm.tolist(),
            "decile_table": decile_table,
        }

    def compute_ks_statistic(self, y_true: np.ndarray, y_prob: np.ndarray) -> float:
        """Kolmogorov-Smirnov statistic."""
        default_probs = np.sort(y_prob[y_true == 1])
        non_default_probs = np.sort(y_prob[y_true == 0])

        all_probs = np.sort(np.unique(np.concatenate([default_probs, non_default_probs])))

        default_cdf = np.searchsorted(default_probs, all_probs, side="right") / len(default_probs)
        non_default_cdf = np.searchsorted(non_default_probs, all_probs, side="right") / len(non_default_probs)

        return float(np.max(np.abs(default_cdf - non_default_cdf)))

    def compute_gini(self, y_true: np.ndarray, y_prob: np.ndarray) -> float:
        return 2 * roc_auc_score(y_true, y_prob) - 1

    def compute_decile_table(self, y_true: np.ndarray, y_prob: np.ndarray) -> list[dict]:
        """Bin predictions into deciles and compute metrics per bin."""
        df = pd.DataFrame({"y_true": y_true, "y_prob": y_prob})
        df["decile"] = pd.qcut(df["y_prob"], 10, labels=False, duplicates="drop") + 1

        table = []
        for decile in sorted(df["decile"].unique()):
            subset = df[df["decile"] == decile]
            table.append({
                "decile": int(decile),
                "count": len(subset),
                "default_count": int(subset["y_true"].sum()),
                "default_rate": float(subset["y_true"].mean()),
                "avg_predicted_pd": float(subset["y_prob"].mean()),
                "min_pd": float(subset["y_prob"].min()),
                "max_pd": float(subset["y_prob"].max()),
            })

        return table

    def evaluate_lgd(self, y_true: np.ndarray, y_pred: np.ndarray) -> dict:
        mask = y_true > 0  # Only evaluate on actual defaults with loss
        if mask.sum() == 0:
            return {"mae": 0.0, "rmse": 0.0, "r2": 0.0}

        return {
            "mae": float(mean_absolute_error(y_true[mask], y_pred[mask])),
            "rmse": float(np.sqrt(mean_squared_error(y_true[mask], y_pred[mask]))),
            "r2": float(r2_score(y_true[mask], y_pred[mask])) if mask.sum() > 1 else 0.0,
        }

    def evaluate_ead(self, y_true: np.ndarray, y_pred: np.ndarray) -> dict:
        mask = y_true > 0
        if mask.sum() == 0:
            return {"mae": 0.0, "rmse": 0.0, "mape": 0.0}

        mape = float(np.mean(np.abs(y_true[mask] - y_pred[mask]) / np.clip(y_true[mask], 1, None)))

        return {
            "mae": float(mean_absolute_error(y_true[mask], y_pred[mask])),
            "rmse": float(np.sqrt(mean_squared_error(y_true[mask], y_pred[mask]))),
            "mape": mape,
        }

    def generate_report(self, results: dict) -> str:
        """Format metrics into a readable report."""
        lines = ["=" * 60, "MODEL EVALUATION REPORT", "=" * 60, ""]

        if "pd" in results:
            pd_r = results["pd"]
            lines.extend([
                "PD Model Performance:",
                f"  AUC-ROC:     {pd_r['auc_roc']:.4f}",
                f"  Gini:        {pd_r['gini']:.4f}",
                f"  KS Statistic:{pd_r['ks_statistic']:.4f}",
                f"  Log Loss:    {pd_r['log_loss']:.4f}",
                f"  Brier Score: {pd_r['brier_score']:.4f}",
                "",
            ])

        if "lgd" in results:
            lgd_r = results["lgd"]
            lines.extend([
                "LGD Model Performance:",
                f"  MAE:  {lgd_r['mae']:.4f}",
                f"  RMSE: {lgd_r['rmse']:.4f}",
                f"  R2:   {lgd_r['r2']:.4f}",
                "",
            ])

        if "ead" in results:
            ead_r = results["ead"]
            lines.extend([
                "EAD Model Performance:",
                f"  MAE:  {ead_r['mae']:.2f}",
                f"  RMSE: {ead_r['rmse']:.2f}",
                f"  MAPE: {ead_r['mape']:.4f}",
                "",
            ])

        lines.append("=" * 60)
        return "\n".join(lines)
