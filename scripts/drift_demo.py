"""Drift monitoring demo using Population Stability Index (PSI).

Simulates production drift by perturbing the training data and measuring
feature-level PSI to detect distributional shifts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from credit_scoring.config.settings import load_settings
from credit_scoring.features.engineering import FeatureEngineer
from credit_scoring.monitoring.drift import DriftDetector


def simulate_drifted_data(
    borrowers: pd.DataFrame, drift_type: str, rng: np.random.Generator
) -> pd.DataFrame:
    """Create a drifted version of borrower data to simulate production shift.

    Args:
        borrowers: Original borrower data.
        drift_type: One of 'economic_downturn', 'demographic_shift', 'seasonal'.
        rng: Random number generator.
    """
    df = borrowers.copy()

    if drift_type == "economic_downturn":
        # Income drops 15%, utilization spikes, more delinquencies
        df["annual_income"] = df["annual_income"] * rng.uniform(0.75, 0.95, len(df))
        df["credit_utilization_ratio"] = (
            df["credit_utilization_ratio"] * rng.uniform(1.1, 1.6, len(df))
        ).clip(0, 2.0)
        df["debt_to_income_ratio"] = (
            df["debt_to_income_ratio"] * rng.uniform(1.1, 1.4, len(df))
        ).clip(0, 5.0)
        df["number_of_delinquencies"] = (
            df["number_of_delinquencies"] + rng.poisson(1, len(df))
        )

    elif drift_type == "demographic_shift":
        # Younger, lower-income population entering the portfolio
        df["age"] = (df["age"] - rng.integers(3, 10, len(df))).clip(18, 100)
        df["employment_length_years"] = (
            df["employment_length_years"] * rng.uniform(0.3, 0.8, len(df))
        ).clip(0, 40)
        df["account_age_months"] = (
            df["account_age_months"] * rng.uniform(0.3, 0.7, len(df))
        ).clip(1, 500).astype(int)

    elif drift_type == "seasonal":
        # Holiday season: higher spending, more online transactions
        df["requested_loan_amount"] = (
            df["requested_loan_amount"] * rng.uniform(1.1, 1.4, len(df))
        )
        df["current_credit_balance"] = (
            df["current_credit_balance"] * rng.uniform(1.05, 1.3, len(df))
        )

    return df


def main():
    settings = load_settings()
    data_dir = settings.data.output_dir
    rng = np.random.default_rng(42)

    # Load training data (our reference distribution)
    print("Loading reference data (training set)...")
    borrowers = pd.read_parquet(data_dir / "borrowers.parquet")
    transactions = pd.read_parquet(data_dir / "transactions.parquet")
    payments = pd.read_parquet(data_dir / "payments.parquet")

    # Compute reference features
    print("Computing reference features...")
    fe = FeatureEngineer()
    ref_features = fe.compute_all(borrowers, transactions, payments, fit=True)
    print(f"  Reference: {ref_features.shape[0]} borrowers, {ref_features.shape[1]} features")

    # Initialize drift detector with reference distribution
    detector = DriftDetector(ref_features)

    # Run three drift scenarios
    scenarios = ["economic_downturn", "demographic_shift", "seasonal"]

    print("\n" + "=" * 70)
    print("DRIFT MONITORING DEMO")
    print("=" * 70)

    for scenario in scenarios:
        print(f"\n{'─' * 70}")
        print(f"Scenario: {scenario.upper().replace('_', ' ')}")
        print(f"{'─' * 70}")

        # Generate drifted borrower data
        drifted_borrowers = simulate_drifted_data(borrowers, scenario, rng)

        # Recompute features with drifted data
        drifted_features = fe.compute_all(
            drifted_borrowers, transactions, payments, fit=False
        )

        # Generate drift report
        report = detector.generate_drift_report(drifted_features)

        print(f"\n  Overall status: {report['overall_status'].upper()}")
        print(
            f"  Features drifted: {report['n_features_drifted']}/{report['n_features_total']}"
        )

        # Show top drifted features
        print("\n  Top 10 features by PSI:")
        print(f"  {'Feature':<35} {'PSI':>8}  {'Status':<10}")
        print(f"  {'─' * 55}")
        for feat in report["feature_drift"][:10]:
            indicator = "🔴" if feat["status"] == "alert" else (
                "🟡" if feat["status"] == "warning" else "🟢"
            )
            print(
                f"  {indicator} {feat['feature']:<33} {feat['psi']:>8.4f}  {feat['status']:<10}"
            )

    # Baseline: same distribution (no drift)
    print(f"\n{'─' * 70}")
    print("Scenario: BASELINE (NO DRIFT)")
    print(f"{'─' * 70}")

    # Sample a different subset from the same distribution
    sample_idx = rng.choice(len(borrowers), size=min(5000, len(borrowers)), replace=False)
    baseline_borrowers = borrowers.iloc[sample_idx].reset_index(drop=True)
    baseline_features = fe.compute_all(
        baseline_borrowers, transactions, payments, fit=False
    )
    baseline_report = detector.generate_drift_report(baseline_features)

    print(f"\n  Overall status: {baseline_report['overall_status'].upper()}")
    print(
        f"  Features drifted: {baseline_report['n_features_drifted']}/{baseline_report['n_features_total']}"
    )
    print("\n  Top 10 features by PSI:")
    print(f"  {'Feature':<35} {'PSI':>8}  {'Status':<10}")
    print(f"  {'─' * 55}")
    for feat in baseline_report["feature_drift"][:10]:
        indicator = "🟢" if feat["status"] == "stable" else "🟡"
        print(
            f"  {indicator} {feat['feature']:<33} {feat['psi']:>8.4f}  {feat['status']:<10}"
        )

    print(f"\n{'=' * 70}")
    print("PSI Thresholds: < 0.10 = Stable | 0.10-0.25 = Warning | >= 0.25 = Alert")
    print("=" * 70)


if __name__ == "__main__":
    main()
