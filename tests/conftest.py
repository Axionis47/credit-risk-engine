"""Shared test fixtures for credit scoring tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from credit_scoring.config.settings import DataSettings, Settings
from credit_scoring.data.synthetic import (
    BorrowerProfileGenerator,
    PaymentHistoryGenerator,
    TransactionGenerator,
)
from credit_scoring.features.engineering import FeatureEngineer


@pytest.fixture(scope="session")
def small_settings() -> Settings:
    """Settings tuned for fast test runs."""
    settings = Settings()
    settings.data = DataSettings(
        n_borrowers=500,
        default_rate=0.10,
        fraud_rate=0.03,
        transaction_months=6,
        avg_transactions_per_month=5,
        random_seed=42,
    )
    return settings


@pytest.fixture(scope="session")
def borrowers(small_settings) -> pd.DataFrame:
    gen = BorrowerProfileGenerator(small_settings.data)
    return gen.generate()


@pytest.fixture(scope="session")
def transactions(small_settings, borrowers) -> pd.DataFrame:
    gen = TransactionGenerator(borrowers, small_settings.data)
    return gen.generate()


@pytest.fixture(scope="session")
def payments(small_settings, borrowers) -> pd.DataFrame:
    gen = PaymentHistoryGenerator(borrowers, small_settings.data)
    return gen.generate()


@pytest.fixture(scope="session")
def feature_matrix(borrowers, transactions, payments) -> pd.DataFrame:
    engineer = FeatureEngineer()
    return engineer.compute_all(borrowers, transactions, payments, fit=True)


@pytest.fixture(scope="session")
def train_test_data(feature_matrix, borrowers):
    """Split features into train and test sets with labels."""
    from sklearn.model_selection import train_test_split

    y = borrowers.set_index("borrower_id").loc[feature_matrix.index, "is_default"].values
    X_train, X_test, y_train, y_test = train_test_split(
        feature_matrix, y, test_size=0.3, stratify=y, random_state=42,
    )
    return X_train, X_test, y_train, y_test


@pytest.fixture
def sample_scoring_request() -> dict:
    """Valid scoring request payload."""
    return {
        "application_id": "test-001",
        "borrower_id": "b-test-001",
        "age": 35,
        "annual_income": 75000.0,
        "employment_length_years": 8.0,
        "employment_type": "employed",
        "home_ownership": "mortgage",
        "existing_credit_lines": 5,
        "total_credit_limit": 50000.0,
        "current_credit_balance": 15000.0,
        "months_since_last_delinquency": None,
        "number_of_delinquencies": 0,
        "debt_to_income_ratio": 0.25,
        "requested_loan_amount": 20000.0,
        "loan_purpose": "debt_consolidation",
        "state": "CA",
        "account_age_months": 120,
        "profile_completeness_score": 0.95,
        "device_type": "desktop",
        "credit_utilization_ratio": 0.30,
    }
