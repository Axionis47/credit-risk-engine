"""Run model evaluation on test data."""

import json

import pandas as pd

from credit_scoring.config.settings import load_settings
from credit_scoring.features.store import FeatureStore
from credit_scoring.models.ensemble import PDEnsemble
from credit_scoring.models.evaluation import ModelEvaluator
from credit_scoring.models.pd_model import LightGBMPDModel, LogisticPDModel, XGBoostPDModel


def main():
    settings = load_settings()
    models_dir = settings.model.models_dir

    # Load models
    pd_models = {}
    if (models_dir / "pd_logistic.joblib").exists():
        pd_models["logistic"] = LogisticPDModel.load(models_dir / "pd_logistic.joblib")
    if (models_dir / "pd_xgboost.joblib").exists():
        pd_models["xgboost"] = XGBoostPDModel.load(models_dir / "pd_xgboost.joblib")
    if (models_dir / "pd_lightgbm.joblib").exists():
        pd_models["lightgbm"] = LightGBMPDModel.load(models_dir / "pd_lightgbm.joblib")

    if not pd_models:
        print("No models found. Run 'make train' first.")
        return

    ensemble = PDEnsemble(pd_models)
    weights_path = models_dir / "ensemble_weights.json"
    if weights_path.exists():
        with open(weights_path) as f:
            ensemble.weights = json.load(f)

    # Load features
    store = FeatureStore(settings.data.output_dir)
    features = store.load_offline("latest")

    # Load targets
    from credit_scoring.data.ingestion import DataLoader
    loader = DataLoader(settings.data.output_dir)
    borrowers = loader.load_borrowers()
    y = borrowers.set_index("borrower_id").loc[features.index, "is_default"].values

    # Evaluate
    evaluator = ModelEvaluator()
    for name, model in pd_models.items():
        preds = model.predict_pd(features)
        metrics = evaluator.evaluate_pd(y, preds)
        print(f"\n{name.upper()}: AUC={metrics['auc_roc']:.4f} KS={metrics['ks_statistic']:.4f} Gini={metrics['gini']:.4f}")

    ensemble_preds = ensemble.predict_pd(features)
    metrics = evaluator.evaluate_pd(y, ensemble_preds)
    print(f"\nENSEMBLE: AUC={metrics['auc_roc']:.4f} KS={metrics['ks_statistic']:.4f} Gini={metrics['gini']:.4f}")


if __name__ == "__main__":
    main()
