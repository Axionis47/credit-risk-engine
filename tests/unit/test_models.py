"""Tests for PD, LGD, EAD, and Fraud models."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from credit_scoring.models.ead_model import EADModel
from credit_scoring.models.ensemble import CreditScoreCalculator, PDEnsemble
from credit_scoring.models.fraud_model import FraudModel
from credit_scoring.models.lgd_model import TwoStageLGDModel
from credit_scoring.models.pd_model import (
    LightGBMPDModel,
    LogisticPDModel,
    XGBoostPDModel,
    create_pd_model,
)


class TestPDModels:
    """Test Probability of Default models."""

    @pytest.fixture(scope="class")
    def trained_lr(self, train_test_data):
        X_train, _, y_train, _ = train_test_data
        model = LogisticPDModel()
        model.fit(X_train, y_train)
        return model

    @pytest.fixture(scope="class")
    def trained_xgb(self, train_test_data):
        X_train, _, y_train, _ = train_test_data
        model = XGBoostPDModel(n_estimators=50)
        model.fit(X_train, y_train)
        return model

    @pytest.fixture(scope="class")
    def trained_lgbm(self, train_test_data):
        X_train, _, y_train, _ = train_test_data
        model = LightGBMPDModel(n_estimators=50)
        model.fit(X_train, y_train)
        return model

    def test_lr_predict_proba_shape(self, trained_lr, train_test_data):
        _, X_test, _, _ = train_test_data
        proba = trained_lr.predict_proba(X_test)
        assert proba.shape == (len(X_test), 2)

    def test_lr_predict_pd_range(self, trained_lr, train_test_data):
        _, X_test, _, _ = train_test_data
        pds = trained_lr.predict_pd(X_test)
        assert (pds >= 0).all() and (pds <= 1).all()

    def test_xgb_predict_pd_range(self, trained_xgb, train_test_data):
        _, X_test, _, _ = train_test_data
        pds = trained_xgb.predict_pd(X_test)
        assert (pds >= 0).all() and (pds <= 1).all()

    def test_lgbm_predict_pd_range(self, trained_lgbm, train_test_data):
        _, X_test, _, _ = train_test_data
        pds = trained_lgbm.predict_pd(X_test)
        assert (pds >= 0).all() and (pds <= 1).all()

    def test_xgb_auc_above_baseline(self, trained_xgb, train_test_data):
        """XGBoost should perform better than random."""
        _, X_test, _, y_test = train_test_data
        pds = trained_xgb.predict_pd(X_test)
        auc = roc_auc_score(y_test, pds)
        assert auc > 0.55, f"AUC {auc:.4f} is barely above random"

    def test_lgbm_auc_above_baseline(self, trained_lgbm, train_test_data):
        _, X_test, _, y_test = train_test_data
        pds = trained_lgbm.predict_pd(X_test)
        auc = roc_auc_score(y_test, pds)
        assert auc > 0.55

    def test_factory_creates_correct_types(self):
        assert isinstance(create_pd_model("logistic"), LogisticPDModel)
        assert isinstance(create_pd_model("xgboost"), XGBoostPDModel)
        assert isinstance(create_pd_model("lightgbm"), LightGBMPDModel)

    def test_factory_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Unknown model type"):
            create_pd_model("invalid_model")

    def test_save_load_roundtrip(self, trained_lr, train_test_data):
        _, X_test, _, _ = train_test_data
        original_pds = trained_lr.predict_pd(X_test)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "model.joblib"
            trained_lr.save(path)
            loaded = LogisticPDModel.load(path)

        loaded_pds = loaded.predict_pd(X_test)
        np.testing.assert_array_almost_equal(original_pds, loaded_pds)

    def test_xgb_save_load_roundtrip(self, trained_xgb, train_test_data):
        _, X_test, _, _ = train_test_data
        original_pds = trained_xgb.predict_pd(X_test)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "model.joblib"
            trained_xgb.save(path)
            loaded = XGBoostPDModel.load(path)

        loaded_pds = loaded.predict_pd(X_test)
        np.testing.assert_array_almost_equal(original_pds, loaded_pds)


class TestPDEnsemble:
    """Test PD ensemble model."""

    def test_ensemble_predict_pd_range(self, train_test_data):
        X_train, X_test, y_train, y_test = train_test_data

        lr = LogisticPDModel()
        lr.fit(X_train, y_train)
        xgb = XGBoostPDModel(n_estimators=50)
        xgb.fit(X_train, y_train)

        ensemble = PDEnsemble({"logistic": lr, "xgboost": xgb})
        pds = ensemble.predict_pd(X_test)
        assert (pds >= 0).all() and (pds <= 1).all()

    def test_ensemble_weight_optimization(self, train_test_data):
        X_train, X_test, y_train, y_test = train_test_data

        lr = LogisticPDModel()
        lr.fit(X_train, y_train)
        xgb = XGBoostPDModel(n_estimators=50)
        xgb.fit(X_train, y_train)

        ensemble = PDEnsemble({"logistic": lr, "xgboost": xgb})
        ensemble.optimize_weights(X_test, y_test)

        # Weights should sum to 1
        total = sum(ensemble.weights.values())
        assert abs(total - 1.0) < 1e-6

        # All weights should be non-negative
        for w in ensemble.weights.values():
            assert w >= 0


class TestLGDModel:
    """Test Loss Given Default model."""

    def test_lgd_predictions_bounded(self, train_test_data):
        X_train, X_test, y_train, _ = train_test_data
        # Fake LGD targets in [0, 1] with some exact zeros (non-default borrowers)
        rng = np.random.default_rng(42)
        y_lgd = rng.beta(2, 5, size=len(X_train))
        y_lgd[: len(y_lgd) // 2] = 0.0  # Half are non-defaulters with zero LGD

        model = TwoStageLGDModel()
        model.fit(X_train, y_lgd)
        preds = model.predict(X_test)

        assert (preds >= 0).all() and (preds <= 1).all()

    def test_lgd_save_load(self, train_test_data):
        X_train, X_test, y_train, _ = train_test_data
        rng = np.random.default_rng(42)
        y_lgd = rng.beta(2, 5, size=len(X_train))
        y_lgd[: len(y_lgd) // 2] = 0.0

        model = TwoStageLGDModel()
        model.fit(X_train, y_lgd)
        original = model.predict(X_test)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "lgd.joblib"
            model.save(path)
            loaded = TwoStageLGDModel.load(path)

        loaded_preds = loaded.predict(X_test)
        np.testing.assert_array_almost_equal(original, loaded_preds)


class TestEADModel:
    """Test Exposure at Default model."""

    def test_ead_predictions_positive(self, train_test_data):
        X_train, X_test, _, _ = train_test_data
        rng = np.random.default_rng(42)
        ccf = rng.beta(2, 8, size=len(X_train))

        model = EADModel()
        model.fit(X_train, ccf)

        drawn = rng.uniform(1000, 10000, size=len(X_test))
        limit = drawn + rng.uniform(5000, 20000, size=len(X_test))

        preds = model.predict(X_test, drawn, limit)
        assert (preds >= 0).all()
        assert (preds <= limit + 1).all()  # Small tolerance


class TestFraudModel:
    """Test Fraud detection model."""

    def test_fraud_score_range(self, train_test_data):
        X_train, X_test, _, _ = train_test_data
        rng = np.random.default_rng(42)
        y_fraud = (rng.random(len(X_train)) < 0.03).astype(int)

        model = FraudModel()
        model.fit(X_train, y_fraud)
        scores = model.predict_fraud_score(X_test)

        assert (scores >= 0).all() and (scores <= 1).all()


class TestCreditScoreCalculator:
    """Test credit score mapping and decision logic."""

    def test_pd_to_credit_score_range(self):
        for pd_val in [0.001, 0.01, 0.05, 0.1, 0.2, 0.5, 0.8]:
            score = CreditScoreCalculator._pd_to_credit_score(pd_val)
            assert 300 <= score <= 850, f"PD={pd_val} -> score={score}"

    def test_low_pd_gives_high_score(self):
        low = CreditScoreCalculator._pd_to_credit_score(0.001)
        high = CreditScoreCalculator._pd_to_credit_score(0.5)
        assert low > high

    def test_risk_tier_assignment(self):
        assert CreditScoreCalculator._assign_risk_tier(0.02) == "low"
        assert CreditScoreCalculator._assign_risk_tier(0.10) == "medium"
        assert CreditScoreCalculator._assign_risk_tier(0.20) == "high"
        assert CreditScoreCalculator._assign_risk_tier(0.40) == "very_high"

    def test_score_batch_output_columns(self, train_test_data):
        X_train, X_test, y_train, _ = train_test_data
        rng = np.random.default_rng(42)

        lr = LogisticPDModel()
        lr.fit(X_train, y_train)
        ensemble = PDEnsemble({"logistic": lr})

        y_lgd = rng.beta(2, 5, size=len(X_train))
        y_lgd[: len(y_lgd) // 2] = 0.0
        lgd = TwoStageLGDModel()
        lgd.fit(X_train, y_lgd)

        ead = EADModel()
        ead.fit(X_train, rng.beta(2, 8, size=len(X_train)))

        fraud = FraudModel()
        fraud.fit(X_train, (rng.random(len(X_train)) < 0.03).astype(int))

        calc = CreditScoreCalculator(ensemble, lgd, ead, fraud)
        result = calc.score_batch(X_test)

        expected_cols = {
            "pd", "lgd", "ead", "expected_loss", "credit_score",
            "risk_tier", "fraud_score", "fraud_flag", "decision",
        }
        assert expected_cols.issubset(set(result.columns))
        assert len(result) == len(X_test)

    def test_decision_values(self, train_test_data):
        X_train, X_test, y_train, _ = train_test_data
        rng = np.random.default_rng(42)

        lr = LogisticPDModel()
        lr.fit(X_train, y_train)
        ensemble = PDEnsemble({"logistic": lr})

        y_lgd = rng.beta(2, 5, size=len(X_train))
        y_lgd[: len(y_lgd) // 2] = 0.0
        lgd = TwoStageLGDModel()
        lgd.fit(X_train, y_lgd)

        ead = EADModel()
        ead.fit(X_train, rng.beta(2, 8, size=len(X_train)))

        fraud = FraudModel()
        fraud.fit(X_train, (rng.random(len(X_train)) < 0.03).astype(int))

        calc = CreditScoreCalculator(ensemble, lgd, ead, fraud)
        result = calc.score_batch(X_test)

        valid_decisions = {"approved", "declined", "manual_review"}
        assert set(result["decision"].unique()).issubset(valid_decisions)
