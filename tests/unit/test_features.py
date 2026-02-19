"""Tests for feature engineering pipeline."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from credit_scoring.features.engineering import FeatureEngineer


class TestFeatureEngineer:
    """Test the FeatureEngineer pipeline."""

    def test_feature_matrix_shape(self, feature_matrix, borrowers):
        """Feature matrix should have one row per borrower."""
        assert feature_matrix.shape[0] == len(borrowers)
        assert feature_matrix.shape[1] > 30  # Should have many features

    def test_no_infinities(self, feature_matrix):
        """No infinite values in the feature matrix."""
        numeric = feature_matrix.select_dtypes(include=[np.number])
        assert not np.isinf(numeric.values).any()

    def test_no_nans(self, feature_matrix):
        """No NaN values after imputation."""
        assert not feature_matrix.isna().any().any()

    def test_all_numeric(self, feature_matrix):
        """All features should be numeric after encoding."""
        for col in feature_matrix.columns:
            assert pd.api.types.is_numeric_dtype(feature_matrix[col]), (
                f"Column {col} is not numeric"
            )

    def test_demographic_features_present(self, feature_matrix):
        """Core demographic features should exist."""
        expected = ["age", "log_annual_income", "employment_length_years", "account_age_months"]
        for col in expected:
            assert col in feature_matrix.columns, f"Missing feature: {col}"

    def test_credit_features_present(self, feature_matrix):
        """Credit history features should exist."""
        expected = ["credit_utilization_ratio", "existing_credit_lines", "debt_to_income_ratio"]
        for col in expected:
            assert col in feature_matrix.columns, f"Missing feature: {col}"

    def test_velocity_features_present(self, feature_matrix):
        """Transaction velocity features should exist."""
        expected = ["txn_count_7d", "txn_count_30d", "txn_count_90d"]
        for col in expected:
            assert col in feature_matrix.columns, f"Missing feature: {col}"

    def test_velocity_features_non_negative(self, feature_matrix):
        """Velocity counts and amounts should be non-negative (excluding trend features)."""
        velocity_cols = [
            c for c in feature_matrix.columns
            if c.startswith("txn_") and "trend" not in c
        ]
        for col in velocity_cols:
            assert (feature_matrix[col] >= 0).all(), f"{col} has negative values"

    def test_payment_features_present(self, feature_matrix):
        """Payment behavior features should exist."""
        expected = ["on_time_payment_rate", "avg_days_past_due", "consecutive_on_time"]
        for col in expected:
            assert col in feature_matrix.columns, f"Missing feature: {col}"

    def test_risk_ratios_present(self, feature_matrix):
        """Risk ratio features should exist."""
        expected = ["loan_to_income_ratio", "utilization_x_dti"]
        for col in expected:
            assert col in feature_matrix.columns, f"Missing feature: {col}"

    def test_categorical_encoded(self, feature_matrix):
        """Categorical columns should be one-hot encoded."""
        raw_categoricals = ["employment_type", "home_ownership", "loan_purpose", "device_type"]
        for col in raw_categoricals:
            assert col not in feature_matrix.columns, f"Raw categorical {col} still present"
        # Should have at least some one-hot columns
        onehot_cols = [c for c in feature_matrix.columns if c.startswith("employment_type_")]
        assert len(onehot_cols) > 0, "No one-hot encoded employment_type columns"

    def test_state_target_encoded(self, feature_matrix):
        """State should be target-encoded, not raw."""
        assert "state" not in feature_matrix.columns
        assert "state_encoded" in feature_matrix.columns
        vals = feature_matrix["state_encoded"]
        assert (vals >= 0).all() and (vals <= 1).all()

    def test_on_time_rate_bounded(self, feature_matrix):
        """On-time payment rate should be between 0 and 1."""
        if "on_time_payment_rate" in feature_matrix.columns:
            vals = feature_matrix["on_time_payment_rate"]
            assert (vals >= 0).all() and (vals <= 1).all()

    def test_no_target_leakage(self, feature_matrix):
        """Target variables should not appear in features."""
        forbidden = ["is_default", "is_fraud", "lgd_value", "ead_value"]
        for col in forbidden:
            assert col not in feature_matrix.columns, f"Target leakage: {col}"

    def test_index_is_borrower_id(self, feature_matrix):
        """Index should be borrower_id."""
        assert feature_matrix.index.name == "borrower_id"

    def test_compute_single(self, sample_scoring_request):
        """Single-row feature computation for API path."""
        engineer = FeatureEngineer()
        result = engineer.compute_single(sample_scoring_request)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert not result.isna().any().any()

    def test_entropy_non_negative(self, feature_matrix):
        """Shannon entropy should be non-negative."""
        if "spend_category_entropy" in feature_matrix.columns:
            assert (feature_matrix["spend_category_entropy"] >= 0).all()

    def test_feature_count_above_minimum(self, feature_matrix):
        """Should produce at least 50 features after encoding."""
        assert feature_matrix.shape[1] >= 50
