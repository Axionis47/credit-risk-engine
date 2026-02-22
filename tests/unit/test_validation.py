"""Tests for data validation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from credit_scoring.data.validation import DataValidator, ValidationResult


class TestValidationResult:
    def test_starts_passing(self):
        result = ValidationResult(passed=True)
        assert result.passed is True
        assert result.checks == []

    def test_failing_check_flips_result(self):
        result = ValidationResult(passed=True)
        result.add_check("test", False, "something broke")
        assert result.passed is False

    def test_passing_check_keeps_result(self):
        result = ValidationResult(passed=True)
        result.add_check("test", True, "all good")
        assert result.passed is True


class TestDataValidator:
    @pytest.fixture
    def validator(self):
        return DataValidator(max_null_fraction=0.05, min_rows=100)

    def test_valid_borrowers_pass(self, validator, borrowers):
        result = validator.validate_borrowers(borrowers)
        assert result.passed is True

    def test_missing_columns_fail(self, validator):
        df = pd.DataFrame({"borrower_id": ["b1"], "age": [30]})
        result = validator.validate_borrowers(df)
        assert result.passed is False
        failed_names = [c["name"] for c in result.checks if not c["passed"]]
        assert "schema" in failed_names or "min_rows" in failed_names

    def test_too_few_rows_fail(self, validator):
        """Fewer rows than threshold should fail."""
        validator.min_rows = 999999
        # Create a small but valid schema
        df = pd.DataFrame({"borrower_id": [f"b{i}" for i in range(10)]})
        result = validator.validate_borrowers(df)
        assert result.passed is False

    def test_null_threshold_enforcement(self, validator, borrowers):
        """Injecting many nulls should fail the null check."""
        df = borrowers.copy()
        n_null = int(len(df) * 0.2)
        df.loc[df.index[:n_null], "age"] = np.nan
        result = validator.validate_borrowers(df)
        failed_names = [c["name"] for c in result.checks if not c["passed"]]
        assert "null_age" in failed_names

    def test_age_range_violation(self, validator, borrowers):
        df = borrowers.copy()
        df.loc[df.index[0], "age"] = 150
        result = validator.validate_borrowers(df)
        failed_names = [c["name"] for c in result.checks if not c["passed"]]
        assert "age_range" in failed_names

    def test_negative_income_fails(self, validator, borrowers):
        df = borrowers.copy()
        df.loc[df.index[0], "annual_income"] = -5000
        result = validator.validate_borrowers(df)
        failed_names = [c["name"] for c in result.checks if not c["passed"]]
        assert "income_positive" in failed_names

    def test_transaction_validation_passes(self, validator, transactions, borrowers):
        bids = set(borrowers["borrower_id"].unique())
        result = validator.validate_transactions(transactions, bids)
        assert result.passed is True

    def test_payment_validation_passes(self, validator, payments, borrowers):
        bids = set(borrowers["borrower_id"].unique())
        result = validator.validate_payments(payments, bids)
        assert result.passed is True

    def test_feature_validation(self, validator, feature_matrix):
        result = validator.validate_features(feature_matrix)
        assert result.passed is True

    def test_feature_validation_catches_inf(self, validator, feature_matrix):
        df = feature_matrix.copy()
        df.iloc[0, 0] = np.inf
        result = validator.validate_features(df)
        failed = [c["name"] for c in result.checks if not c["passed"]]
        assert "no_infinities" in failed
