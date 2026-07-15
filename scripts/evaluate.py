"""Run model evaluation on the held-out validation and test splits.

Reconstructs the exact deterministic 65/15/20 split used by training.py
(stratified on the default label, random_state=42), so metrics here are
comparable across runs and never include rows the models trained on.

An earlier version of this script scored the full dataset, training rows
included, which inflated the most flexible model's AUC (LightGBM printed
0.9418 full-data vs 0.8332 on the true test split). Results are written to
evidence/heldout_metrics.json so the numbers live in the repo, not in prose.
"""

import json
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

from credit_scoring.config.settings import load_settings
from credit_scoring.data.ingestion import DataLoader
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

    # Load features and targets
    store = FeatureStore(settings.data.output_dir)
    features = store.load_offline("latest")

    loader = DataLoader(settings.data.output_dir)
    borrowers = loader.load_borrowers()
    y = borrowers.set_index("borrower_id").loc[features.index, "is_default"].values

    # Reconstruct training.py's split: train (65%) / validation (15%) / test (20%)
    idx = np.arange(len(features))
    idx_trainval, idx_test = train_test_split(
        idx,
        test_size=settings.model.test_size,
        stratify=y,
        random_state=42,
    )
    relative_val = settings.model.validation_size / (1 - settings.model.test_size)
    _, idx_val = train_test_split(
        idx_trainval,
        test_size=relative_val,
        stratify=y[idx_trainval],
        random_state=42,
    )

    evaluator = ModelEvaluator()
    results = {
        "split": {
            "scheme": "65/15/20 stratified, random_state=42 (matches training.py)",
            "n_total": int(len(features)),
            "n_validation": int(len(idx_val)),
            "n_test": int(len(idx_test)),
            "test_default_rate": round(float(y[idx_test].mean()), 4),
        },
        "validation": {},
        "test": {},
    }

    for part, ids in [("validation", idx_val), ("test", idx_test)]:
        X_part, y_part = features.iloc[ids], y[ids]
        print(f"\n=== {part.upper()} ({len(ids)} rows) ===")
        scored = dict(pd_models)
        scored["ensemble"] = ensemble
        for name, model in scored.items():
            metrics = evaluator.evaluate_pd(y_part, model.predict_pd(X_part))
            results[part][name] = {
                "auc_roc": round(float(metrics["auc_roc"]), 4),
                "ks_statistic": round(float(metrics["ks_statistic"]), 4),
                "gini": round(float(metrics["gini"]), 4),
            }
            print(
                f"{name.upper()}: AUC={metrics['auc_roc']:.4f} "
                f"KS={metrics['ks_statistic']:.4f} Gini={metrics['gini']:.4f}"
            )

    out_path = Path("evidence") / "heldout_metrics.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
