"""Performance tests: verify model quality thresholds."""

from __future__ import annotations

import time

import pytest
from sklearn.metrics import roc_auc_score

from credit_scoring.models.pd_model import LogisticPDModel, XGBoostPDModel


class TestModelPerformance:
    """Verify model quality on test data."""

    @pytest.fixture(scope="class")
    def trained_models(self, train_test_data):
        X_train, _, y_train, _ = train_test_data
        lr = LogisticPDModel()
        lr.fit(X_train, y_train)
        xgb = XGBoostPDModel(n_estimators=100)
        xgb.fit(X_train, y_train)
        return {"logistic": lr, "xgboost": xgb}

    def test_xgboost_auc_minimum(self, trained_models, train_test_data):
        """XGBoost AUC should be above 0.60 on test data."""
        _, X_test, _, y_test = train_test_data
        pds = trained_models["xgboost"].predict_pd(X_test)
        auc = roc_auc_score(y_test, pds)
        assert auc >= 0.60, f"XGBoost AUC {auc:.4f} below 0.60 threshold"

    def test_logistic_auc_minimum(self, trained_models, train_test_data):
        """Logistic regression AUC should be above 0.55."""
        _, X_test, _, y_test = train_test_data
        pds = trained_models["logistic"].predict_pd(X_test)
        auc = roc_auc_score(y_test, pds)
        assert auc >= 0.55, f"LR AUC {auc:.4f} below 0.55 threshold"

    def test_ks_statistic_positive(self, trained_models, train_test_data):
        """KS statistic should be meaningfully positive."""
        from scipy.stats import ks_2samp

        _, X_test, _, y_test = train_test_data
        pds = trained_models["xgboost"].predict_pd(X_test)

        default_pds = pds[y_test == 1]
        non_default_pds = pds[y_test == 0]
        ks_stat, _ = ks_2samp(default_pds, non_default_pds)
        assert ks_stat > 0.10, f"KS statistic {ks_stat:.4f} too low"


class TestInferenceLatency:
    """Verify that scoring is fast enough for production."""

    def test_single_prediction_latency(self, train_test_data):
        """Single prediction should complete in under 50ms."""
        X_train, X_test, y_train, _ = train_test_data
        model = XGBoostPDModel(n_estimators=100)
        model.fit(X_train, y_train)

        single = X_test.iloc[:1]

        # Warm up
        model.predict_pd(single)

        start = time.monotonic()
        for _ in range(100):
            model.predict_pd(single)
        elapsed = time.monotonic() - start
        avg_ms = (elapsed / 100) * 1000

        assert avg_ms < 50, f"Average latency {avg_ms:.2f}ms exceeds 50ms"

    def test_batch_prediction_throughput(self, train_test_data):
        """Batch of 100 predictions should complete in under 500ms."""
        X_train, X_test, y_train, _ = train_test_data
        model = XGBoostPDModel(n_estimators=100)
        model.fit(X_train, y_train)

        batch = X_test.iloc[:100]

        # Warm up
        model.predict_pd(batch)

        start = time.monotonic()
        model.predict_pd(batch)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 500, f"Batch latency {elapsed_ms:.2f}ms exceeds 500ms"
