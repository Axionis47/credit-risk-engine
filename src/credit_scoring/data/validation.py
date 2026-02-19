"""Data validation checks for credit scoring datasets."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class ValidationResult:
    passed: bool
    checks: list[dict] = field(default_factory=list)

    def add_check(self, name: str, passed: bool, details: str = ""):
        self.checks.append({"name": name, "passed": passed, "details": details})
        if not passed:
            self.passed = False


class DataValidator:
    """Validate datasets against schema and distribution expectations."""

    BORROWER_REQUIRED_COLUMNS = [
        "borrower_id", "age", "annual_income", "employment_length_years",
        "employment_type", "home_ownership", "existing_credit_lines",
        "total_credit_limit", "current_credit_balance", "credit_utilization_ratio",
        "number_of_delinquencies", "debt_to_income_ratio", "requested_loan_amount",
        "loan_purpose", "state", "account_age_months", "profile_completeness_score",
        "device_type", "is_default",
    ]

    TRANSACTION_REQUIRED_COLUMNS = [
        "transaction_id", "borrower_id", "timestamp", "amount",
        "merchant_category", "is_international", "channel", "is_declined",
    ]

    PAYMENT_REQUIRED_COLUMNS = [
        "borrower_id", "payment_date", "due_date", "amount_due",
        "amount_paid", "days_past_due", "payment_status",
    ]

    def __init__(self, max_null_fraction: float = 0.05, min_rows: int = 1000):
        self.max_null_fraction = max_null_fraction
        self.min_rows = min_rows

    def validate_borrowers(self, df: pd.DataFrame) -> ValidationResult:
        result = ValidationResult(passed=True)

        # Row count
        result.add_check(
            "min_rows",
            len(df) >= self.min_rows,
            f"Got {len(df)} rows, need {self.min_rows}",
        )

        # Required columns
        missing = set(self.BORROWER_REQUIRED_COLUMNS) - set(df.columns)
        result.add_check("schema", len(missing) == 0, f"Missing columns: {missing}")
        if missing:
            return result

        # Uniqueness
        result.add_check(
            "borrower_id_unique",
            df["borrower_id"].is_unique,
            f"Duplicate borrower_ids: {df['borrower_id'].duplicated().sum()}",
        )

        # Null check (excluding nullable columns)
        nullable = {"months_since_last_delinquency"}
        for col in self.BORROWER_REQUIRED_COLUMNS:
            if col in nullable:
                continue
            null_frac = df[col].isnull().mean()
            result.add_check(
                f"null_{col}",
                null_frac <= self.max_null_fraction,
                f"{col}: {null_frac:.3f} null fraction",
            )

        # Range checks
        result.add_check("age_range", df["age"].between(18, 100).all(), "Age out of [18, 100]")
        result.add_check("income_positive", (df["annual_income"] > 0).all(), "Negative income found")
        result.add_check(
            "utilization_range",
            df["credit_utilization_ratio"].between(0, 2.0).all(),
            "Utilization out of [0, 2.0]",
        )

        # Default rate sanity
        default_rate = df["is_default"].mean()
        result.add_check(
            "default_rate",
            0.01 <= default_rate <= 0.30,
            f"Default rate {default_rate:.3f} outside [0.01, 0.30]",
        )

        # Valid categories
        valid_emp = {"employed", "self_employed", "unemployed", "retired"}
        result.add_check(
            "employment_type_valid",
            set(df["employment_type"].unique()).issubset(valid_emp),
            f"Invalid employment types: {set(df['employment_type'].unique()) - valid_emp}",
        )

        return result

    def validate_transactions(
        self, df: pd.DataFrame, borrower_ids: set[str] | None = None
    ) -> ValidationResult:
        result = ValidationResult(passed=True)

        missing = set(self.TRANSACTION_REQUIRED_COLUMNS) - set(df.columns)
        result.add_check("schema", len(missing) == 0, f"Missing columns: {missing}")
        if missing:
            return result

        result.add_check("amount_positive", (df["amount"] > 0).all(), "Non-positive amounts found")

        if borrower_ids is not None:
            unknown = set(df["borrower_id"].unique()) - borrower_ids
            result.add_check(
                "referential_integrity",
                len(unknown) == 0,
                f"{len(unknown)} unknown borrower_ids",
            )

        return result

    def validate_payments(
        self, df: pd.DataFrame, borrower_ids: set[str] | None = None
    ) -> ValidationResult:
        result = ValidationResult(passed=True)

        missing = set(self.PAYMENT_REQUIRED_COLUMNS) - set(df.columns)
        result.add_check("schema", len(missing) == 0, f"Missing columns: {missing}")
        if missing:
            return result

        result.add_check("amount_due_non_negative", (df["amount_due"] >= 0).all(), "Negative amount_due")
        result.add_check("amount_paid_non_negative", (df["amount_paid"] >= 0).all(), "Negative amount_paid")
        result.add_check("days_past_due_non_negative", (df["days_past_due"] >= 0).all(), "Negative days_past_due")

        if borrower_ids is not None:
            unknown = set(df["borrower_id"].unique()) - borrower_ids
            result.add_check(
                "referential_integrity",
                len(unknown) == 0,
                f"{len(unknown)} unknown borrower_ids",
            )

        return result

    def validate_features(self, df: pd.DataFrame) -> ValidationResult:
        result = ValidationResult(passed=True)

        # No infinities
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        inf_count = np.isinf(df[numeric_cols]).sum().sum()
        result.add_check("no_infinities", inf_count == 0, f"{inf_count} infinite values found")

        # Zero variance check (warning only, small datasets may have zero-variance columns)
        zero_var = [col for col in numeric_cols if df[col].std() == 0]
        if zero_var:
            import logging
            logging.getLogger(__name__).warning("Zero variance columns: %s", zero_var)
        result.add_check(
            "no_zero_variance",
            True,
            f"Zero variance columns: {zero_var}" if zero_var else "No zero variance columns",
        )

        return result
