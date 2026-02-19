"""End-to-end training pipeline for credit scoring models."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

from credit_scoring.config.settings import Settings
from credit_scoring.data.ingestion import DataLoader
from credit_scoring.data.validation import DataValidator
from credit_scoring.features.engineering import FeatureEngineer
from credit_scoring.features.store import FeatureStore
from credit_scoring.models.ead_model import EADModel
from credit_scoring.models.ensemble import CreditScoreCalculator, PDEnsemble
from credit_scoring.models.evaluation import ModelEvaluator
from credit_scoring.models.fraud_model import FraudModel
from credit_scoring.models.lgd_model import TwoStageLGDModel
from credit_scoring.models.pd_model import create_pd_model


class TrainingPipeline:
    """Orchestrates end-to-end model training."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.evaluator = ModelEvaluator()

    def run(self) -> dict:
        """Execute full training pipeline. Returns evaluation results."""
        print("=" * 60)
        print("CREDIT SCORING TRAINING PIPELINE")
        print("=" * 60)

        # Step 1: Load data
        print("\n[1/14] Loading data...")
        loader = DataLoader(self.settings.data.output_dir)
        data = loader.load_all()
        borrowers = data["borrowers"]
        transactions = data["transactions"]
        payments = data["payments"]
        print(f"  Borrowers: {len(borrowers)}, Transactions: {len(transactions)}, Payments: {len(payments)}")

        # Step 2: Validate
        print("\n[2/14] Validating data...")
        validator = DataValidator()
        bv = validator.validate_borrowers(borrowers)
        if not bv.passed:
            failed = [c for c in bv.checks if not c["passed"]]
            print(f"  WARNING: Borrower validation failed: {failed}")

        # Step 3: Compute features
        print("\n[3/14] Computing features...")
        engineer = FeatureEngineer()
        features = engineer.compute_all(borrowers, transactions, payments, fit=True)
        print(f"  Feature matrix: {features.shape[0]} rows x {features.shape[1]} columns")

        # Save features
        store = FeatureStore(self.settings.data.output_dir)
        store.save_offline(features, "latest")

        # Step 4: Prepare targets and split
        print("\n[4/14] Splitting train/validation/test...")
        borrower_data = borrowers.set_index("borrower_id").loc[features.index]
        y_default = borrower_data["is_default"].values
        y_fraud = borrower_data["is_fraud"].values
        y_lgd = borrower_data["lgd_value"].values
        y_ead = borrower_data["ead_value"].values
        drawn = borrower_data["current_credit_balance"].values
        limit = borrower_data["total_credit_limit"].values

        # Build aligned DataFrame so all targets split consistently
        idx = np.arange(len(features))

        # Split: train (65%) / validation (15%) / test (20%)
        idx_trainval, idx_test = train_test_split(
            idx, test_size=self.settings.model.test_size,
            stratify=y_default, random_state=42,
        )
        relative_val = self.settings.model.validation_size / (1 - self.settings.model.test_size)
        idx_train, idx_val = train_test_split(
            idx_trainval, test_size=relative_val,
            stratify=y_default[idx_trainval], random_state=42,
        )

        X_train, X_val, X_test = features.iloc[idx_train], features.iloc[idx_val], features.iloc[idx_test]
        y_train, y_val, y_test = y_default[idx_train], y_default[idx_val], y_default[idx_test]

        print(f"  Train: {len(X_train)}, Validation: {len(X_val)}, Test: {len(X_test)}")
        print(f"  Default rate: train={y_train.mean():.3f}, val={y_val.mean():.3f}, test={y_test.mean():.3f}")

        # Step 5: Optuna tuning for XGBoost
        print("\n[5/14] Tuning XGBoost hyperparameters...")
        best_xgb_params = self._tune_xgboost(X_train, y_train)
        print(f"  Best params: {best_xgb_params}")

        # Step 6: Train PD models
        print("\n[6/14] Training PD models...")
        pd_models = {}

        print("  Training Logistic Regression...")
        lr = create_pd_model("logistic")
        lr.fit(X_train, y_train)
        pd_models["logistic"] = lr

        print("  Training XGBoost...")
        xgb = create_pd_model("xgboost", **best_xgb_params)
        xgb.fit(X_train, y_train)
        pd_models["xgboost"] = xgb

        print("  Training LightGBM...")
        lgbm = create_pd_model("lightgbm")
        lgbm.fit(X_train, y_train)
        pd_models["lightgbm"] = lgbm

        # Step 6b: TensorFlow model (optional)
        tf_model = None
        if self.settings.model.deep_model_enabled:
            print("  Training TensorFlow Wide & Deep...")
            try:
                from credit_scoring.models.deep_model import TensorFlowPDModel
                tf_model = TensorFlowPDModel(
                    embedding_dim=self.settings.deep_model.embedding_dim,
                    dense_layers=self.settings.deep_model.dense_layers,
                    dropout_rate=self.settings.deep_model.dropout_rate,
                    learning_rate=self.settings.deep_model.learning_rate,
                    batch_size=self.settings.deep_model.batch_size,
                    epochs=self.settings.deep_model.epochs,
                    early_stopping_patience=self.settings.deep_model.early_stopping_patience,
                )
                tf_model.fit(X_train, y_train)
                pd_models["tensorflow"] = tf_model
            except Exception as e:
                print(f"  WARNING: TensorFlow training failed: {e}")
                print("  Continuing without TF model...")

        # Step 7: Ensemble
        print("\n[7/14] Building PD ensemble...")
        ensemble = PDEnsemble(pd_models)
        ensemble.optimize_weights(X_val, y_val)
        print(f"  Ensemble weights: {ensemble.weights}")

        # Step 8: Train LGD model
        print("\n[8/14] Training LGD model...")
        y_lgd_train = y_lgd[idx_train]
        lgd_model = TwoStageLGDModel()
        lgd_model.fit(X_train, y_lgd_train)

        # Step 9: Train EAD model
        print("\n[9/14] Training EAD model...")
        drawn_train = drawn[idx_train]
        limit_train = limit[idx_train]
        ead_train = y_ead[idx_train]

        diff = limit_train - drawn_train
        safe_mask = diff > 0
        ccf_actual = np.zeros_like(ead_train)
        ccf_actual[safe_mask] = (ead_train[safe_mask] - drawn_train[safe_mask]) / diff[safe_mask]
        ccf_actual = np.clip(ccf_actual, 0, 1)

        ead_model = EADModel()
        ead_model.fit(X_train, ccf_actual)

        # Step 10: Train Fraud model
        print("\n[10/14] Training Fraud model...")
        y_fraud_train = y_fraud[idx_train]
        fraud_model = FraudModel()
        fraud_model.fit(X_train, y_fraud_train)

        # Step 11: Evaluate
        print("\n[11/14] Evaluating models...")
        results = {}

        # PD evaluation per model
        for name, model in pd_models.items():
            pd_preds = model.predict_pd(X_test)
            pd_eval = self.evaluator.evaluate_pd(y_test, pd_preds)
            results[f"pd_{name}"] = pd_eval
            print(f"  {name}: AUC={pd_eval['auc_roc']:.4f}, KS={pd_eval['ks_statistic']:.4f}, Gini={pd_eval['gini']:.4f}")

        # Ensemble evaluation
        ensemble_preds = ensemble.predict_pd(X_test)
        ensemble_eval = self.evaluator.evaluate_pd(y_test, ensemble_preds)
        results["pd_ensemble"] = ensemble_eval
        print(f"  ENSEMBLE: AUC={ensemble_eval['auc_roc']:.4f}, KS={ensemble_eval['ks_statistic']:.4f}, Gini={ensemble_eval['gini']:.4f}")

        # LGD evaluation
        y_lgd_test = y_lgd[idx_test]
        lgd_preds = lgd_model.predict(X_test)
        lgd_eval = self.evaluator.evaluate_lgd(y_lgd_test, lgd_preds)
        results["lgd"] = lgd_eval
        print(f"  LGD: MAE={lgd_eval['mae']:.4f}, RMSE={lgd_eval['rmse']:.4f}")

        # EAD evaluation
        y_ead_test = y_ead[idx_test]
        drawn_test = drawn[idx_test]
        limit_test = limit[idx_test]
        ead_preds = ead_model.predict(X_test, drawn_test, limit_test)
        ead_eval = self.evaluator.evaluate_ead(y_ead_test, ead_preds)
        results["ead"] = ead_eval
        print(f"  EAD: MAE={ead_eval['mae']:.2f}, RMSE={ead_eval['rmse']:.2f}")

        # Step 12: Performance gate
        print("\n[12/14] Performance gate check...")
        best_auc = ensemble_eval["auc_roc"]
        results["pd_auc"] = best_auc
        results["pd_ks"] = ensemble_eval["ks_statistic"]
        results["pd_gini"] = ensemble_eval["gini"]

        if best_auc < self.settings.model.min_auc_threshold:
            print(f"  FAILED: AUC {best_auc:.4f} < threshold {self.settings.model.min_auc_threshold}")
        else:
            print(f"  PASSED: AUC {best_auc:.4f} >= threshold {self.settings.model.min_auc_threshold}")

        # Step 13: Save models
        print("\n[13/14] Saving models...")
        models_dir = self.settings.model.models_dir
        models_dir.mkdir(parents=True, exist_ok=True)

        lr.save(models_dir / "pd_logistic.joblib")
        xgb.save(models_dir / "pd_xgboost.joblib")
        lgbm.save(models_dir / "pd_lightgbm.joblib")

        if tf_model is not None:
            tf_model.save(models_dir / "tf_pd_model")

        lgd_model.save(models_dir / "lgd_model.joblib")
        ead_model.save(models_dir / "ead_model.joblib")
        fraud_model.save(models_dir / "fraud_model.joblib")

        # Save ensemble weights
        with open(models_dir / "ensemble_weights.json", "w") as f:
            json.dump(ensemble.weights, f, indent=2)

        # Save SHAP background data
        background = X_train.sample(min(500, len(X_train)), random_state=42)
        background.to_parquet(models_dir / "shap_background.parquet")

        # Step 14: Log to MLflow
        print("\n[14/14] Logging to MLflow...")
        self._log_to_mlflow(results, ensemble.weights)

        # Report
        report = self.evaluator.generate_report({
            "pd": ensemble_eval,
            "lgd": lgd_eval,
            "ead": ead_eval,
        })
        print(f"\n{report}")

        return results

    def _tune_xgboost(self, X_train: pd.DataFrame, y_train: np.ndarray) -> dict:
        """Optuna hyperparameter tuning for XGBoost."""
        try:
            import optuna
            optuna.logging.set_verbosity(optuna.logging.WARNING)

            def objective(trial):
                params = {
                    "max_depth": trial.suggest_int("max_depth", 3, 10),
                    "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                    "n_estimators": trial.suggest_int("n_estimators", 100, 500),
                    "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                    "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                    "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                    "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
                    "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
                }
                from xgboost import XGBClassifier
                model = XGBClassifier(
                    **params, objective="binary:logistic",
                    eval_metric="auc", random_state=42, verbosity=0,
                )
                cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
                scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="roc_auc")
                return scores.mean()

            study = optuna.create_study(direction="maximize")
            n_trials = min(self.settings.model.n_optuna_trials, 20)  # Cap for speed
            study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
            return study.best_params

        except ImportError:
            print("  Optuna not available, using default params")
            return {}

    def _log_to_mlflow(self, results: dict, weights: dict):
        """Log metrics and parameters to MLflow."""
        try:
            import mlflow

            mlflow.set_tracking_uri(self.settings.mlflow_tracking_uri)
            mlflow.set_experiment("credit_scoring")

            with mlflow.start_run(run_name="training_pipeline"):
                mlflow.log_param("n_borrowers", self.settings.data.n_borrowers)
                mlflow.log_param("default_rate", self.settings.data.default_rate)
                mlflow.log_param("deep_model_enabled", self.settings.model.deep_model_enabled)

                for key, value in weights.items():
                    mlflow.log_param(f"ensemble_weight_{key}", round(value, 4))

                mlflow.log_metric("pd_ensemble_auc", results.get("pd_auc", 0))
                mlflow.log_metric("pd_ensemble_ks", results.get("pd_ks", 0))
                mlflow.log_metric("pd_ensemble_gini", results.get("pd_gini", 0))

                if "lgd" in results:
                    mlflow.log_metric("lgd_mae", results["lgd"]["mae"])
                if "ead" in results:
                    mlflow.log_metric("ead_mae", results["ead"]["mae"])

        except Exception as e:
            print(f"  MLflow logging skipped: {e}")
