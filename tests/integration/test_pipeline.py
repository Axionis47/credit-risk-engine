"""Integration test for end-to-end training pipeline."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from credit_scoring.config.settings import DataSettings, ModelSettings, Settings
from credit_scoring.data.synthetic import (
    BorrowerProfileGenerator,
    PaymentHistoryGenerator,
    TransactionGenerator,
)


class TestTrainingPipeline:
    """End-to-end pipeline integration test on small synthetic data."""

    @pytest.fixture(scope="class")
    def pipeline_settings(self, tmp_path_factory):
        tmpdir = tmp_path_factory.mktemp("pipeline")
        data_dir = tmpdir / "data"
        data_dir.mkdir()
        models_dir = tmpdir / "models"
        models_dir.mkdir()

        settings = Settings()
        settings.data = DataSettings(
            n_borrowers=300,
            default_rate=0.10,
            fraud_rate=0.03,
            transaction_months=3,
            avg_transactions_per_month=3,
            random_seed=42,
            output_dir=data_dir,
        )
        settings.model = ModelSettings(
            n_optuna_trials=2,
            cv_folds=2,
            min_auc_threshold=0.55,
            models_dir=models_dir,
            deep_model_enabled=False,  # Skip TF for speed in integration test
        )
        return settings

    @pytest.fixture(scope="class")
    def generated_data(self, pipeline_settings):
        """Generate and save data to disk for the pipeline."""
        s = pipeline_settings.data
        gen_b = BorrowerProfileGenerator(s)
        borrowers = gen_b.generate()
        borrowers.to_parquet(s.output_dir / "borrowers.parquet", index=False)

        gen_t = TransactionGenerator(borrowers, s)
        txns = gen_t.generate()
        txns.to_parquet(s.output_dir / "transactions.parquet", index=False)

        gen_p = PaymentHistoryGenerator(borrowers, s)
        payments = gen_p.generate()
        payments.to_parquet(s.output_dir / "payments.parquet", index=False)

        return s.output_dir

    def test_full_pipeline_runs(self, pipeline_settings, generated_data):
        """Pipeline should complete without errors on small data."""
        from credit_scoring.models.training import TrainingPipeline

        pipeline = TrainingPipeline(pipeline_settings)
        results = pipeline.run()

        assert isinstance(results, dict)
        assert "pd_auc" in results
        assert results["pd_auc"] > 0.5

    def test_models_saved(self, pipeline_settings, generated_data):
        """Trained models should be saved to disk."""
        models_dir = pipeline_settings.model.models_dir
        assert (models_dir / "pd_logistic.joblib").exists()
        assert (models_dir / "pd_xgboost.joblib").exists()
        assert (models_dir / "pd_lightgbm.joblib").exists()
        assert (models_dir / "lgd_model.joblib").exists()
        assert (models_dir / "ead_model.joblib").exists()
        assert (models_dir / "fraud_model.joblib").exists()
        assert (models_dir / "ensemble_weights.json").exists()
        assert (models_dir / "shap_background.parquet").exists()
