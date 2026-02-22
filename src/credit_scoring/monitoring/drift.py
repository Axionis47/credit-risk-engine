"""Data and prediction drift detection using PSI."""

from __future__ import annotations

import numpy as np
import pandas as pd


class DriftDetector:
    """Detect data and concept drift using Population Stability Index."""

    def __init__(self, reference_data: pd.DataFrame, n_bins: int = 10):
        self.n_bins = n_bins
        self.reference_distributions = self._compute_distributions(reference_data)

    def _compute_distributions(self, df: pd.DataFrame) -> dict:
        distributions = {}
        for col in df.select_dtypes(include=[np.number]).columns:
            values = df[col].dropna().values
            if len(values) == 0:
                continue
            try:
                _, bin_edges = np.histogram(values, bins=self.n_bins)
                counts, _ = np.histogram(values, bins=bin_edges)
                distributions[col] = {
                    "bin_edges": bin_edges,
                    "proportions": counts / counts.sum(),
                }
            except (ValueError, IndexError):
                continue
        return distributions

    def compute_psi(self, current_data: pd.DataFrame) -> dict[str, float]:
        """Compute PSI for each feature.

        PSI < 0.10: stable
        0.10 <= PSI < 0.25: moderate shift
        PSI >= 0.25: significant shift
        """
        results = {}
        for col, ref_dist in self.reference_distributions.items():
            if col not in current_data.columns:
                continue

            values = current_data[col].dropna().values
            if len(values) == 0:
                continue

            counts, _ = np.histogram(values, bins=ref_dist["bin_edges"])
            current_props = counts / max(counts.sum(), 1)

            ref_props = ref_dist["proportions"]

            # Avoid zero division
            ref_props = np.clip(ref_props, 1e-6, None)
            current_props = np.clip(current_props, 1e-6, None)

            psi = float(np.sum((current_props - ref_props) * np.log(current_props / ref_props)))
            results[col] = psi

        return results

    def compute_feature_drift(self, current_data: pd.DataFrame) -> list[dict]:
        """Compute drift status for each feature."""
        psi_values = self.compute_psi(current_data)
        results = []

        for feature, psi in psi_values.items():
            if psi < 0.10:
                status = "stable"
            elif psi < 0.25:
                status = "warning"
            else:
                status = "alert"

            results.append(
                {
                    "feature": feature,
                    "psi": round(psi, 4),
                    "status": status,
                }
            )

        return sorted(results, key=lambda x: x["psi"], reverse=True)

    def generate_drift_report(self, current_data: pd.DataFrame) -> dict:
        """Full drift report."""
        feature_drift = self.compute_feature_drift(current_data)

        statuses = [d["status"] for d in feature_drift]
        if "alert" in statuses:
            overall = "alert"
        elif "warning" in statuses:
            overall = "warning"
        else:
            overall = "stable"

        return {
            "overall_status": overall,
            "feature_drift": feature_drift,
            "n_features_drifted": sum(1 for s in statuses if s != "stable"),
            "n_features_total": len(feature_drift),
        }
