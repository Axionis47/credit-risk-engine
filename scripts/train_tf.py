"""Train TensorFlow Wide & Deep model separately and add to existing ensemble."""

import os
import sys

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
sys.stdout.reconfigure(line_buffering=True)

import json
from pathlib import Path

import numpy as np
import pandas as pd

from credit_scoring.config.settings import load_settings
from credit_scoring.features.engineering import FeatureEngineer
from credit_scoring.models.deep_model import TensorFlowPDModel

print("=" * 60, flush=True)
print("TENSORFLOW WIDE & DEEP TRAINING", flush=True)
print("=" * 60, flush=True)

settings = load_settings()
data_dir = settings.data.output_dir
models_dir = settings.model.models_dir

# Load data
print("\n[1] Loading data...", flush=True)
borrowers = pd.read_parquet(data_dir / "borrowers.parquet")
transactions = pd.read_parquet(data_dir / "transactions.parquet")
payments = pd.read_parquet(data_dir / "payments.parquet")
print(f"  {len(borrowers)} borrowers", flush=True)

# Compute features
print("\n[2] Computing features...", flush=True)
fe = FeatureEngineer()
features = fe.compute_all(borrowers, transactions, payments, fit=True)
print(f"  {features.shape[1]} features", flush=True)

# Align targets
print("\n[3] Preparing train/test split...", flush=True)
from sklearn.model_selection import train_test_split

borrower_data = borrowers.set_index("borrower_id").loc[features.index]
y = borrower_data["is_default"].values

idx = np.arange(len(features))
idx_train, idx_test = train_test_split(
    idx, test_size=0.20, stratify=y, random_state=42,
)

X_train = features.iloc[idx_train]
X_test = features.iloc[idx_test]
y_train = y[idx_train]
y_test = y[idx_test]
print(f"  Train: {len(X_train)}, Test: {len(X_test)}", flush=True)

# Train TF model
print("\n[4] Training TensorFlow Wide & Deep...", flush=True)
tf_model = TensorFlowPDModel(
    embedding_dim=settings.deep_model.embedding_dim,
    dense_layers=settings.deep_model.dense_layers,
    dropout_rate=settings.deep_model.dropout_rate,
    learning_rate=settings.deep_model.learning_rate,
    batch_size=settings.deep_model.batch_size,
    epochs=settings.deep_model.epochs,
    early_stopping_patience=settings.deep_model.early_stopping_patience,
)
tf_model.fit(X_train, y_train)

# Evaluate
print("\n[5] Evaluating...", flush=True)
from sklearn.metrics import roc_auc_score

proba = tf_model.predict_proba(X_test)[:, 1]
auc = roc_auc_score(y_test, proba)
print(f"  TensorFlow AUC: {auc:.4f}", flush=True)

# Save model
print("\n[6] Saving model...", flush=True)
tf_model.save(models_dir / "tf_pd_model")
print(f"  Saved to {models_dir}/tf_pd_model/", flush=True)

# Update ensemble weights to include TF
print("\n[7] Updating ensemble weights...", flush=True)
weights_path = models_dir / "ensemble_weights.json"
if weights_path.exists():
    with open(weights_path) as f:
        weights = json.load(f)
else:
    weights = {}

# Re-optimize weights with TF included
import joblib

from credit_scoring.models.ensemble import PDEnsemble
from credit_scoring.models.pd_model import (
    LightGBMPDModel,
    LogisticPDModel,
    XGBoostPDModel,
)

pd_models = {}
if (models_dir / "pd_logistic.joblib").exists():
    pd_models["logistic"] = LogisticPDModel.load(models_dir / "pd_logistic.joblib")
if (models_dir / "pd_xgboost.joblib").exists():
    pd_models["xgboost"] = XGBoostPDModel.load(models_dir / "pd_xgboost.joblib")
if (models_dir / "pd_lightgbm.joblib").exists():
    pd_models["lightgbm"] = LightGBMPDModel.load(models_dir / "pd_lightgbm.joblib")
pd_models["tensorflow"] = tf_model

ensemble = PDEnsemble(pd_models)
ensemble.optimize_weights(X_test, y_test)

# Print new weights
print("\n  Updated ensemble weights:", flush=True)
for name, w in sorted(ensemble.weights.items(), key=lambda x: -x[1]):
    print(f"    {name}: {w:.4f}", flush=True)

# Compute ensemble AUC
ensemble_pd = ensemble.predict_pd(X_test)
ensemble_auc = roc_auc_score(y_test, ensemble_pd)
print(f"\n  4-model Ensemble AUC: {ensemble_auc:.4f}", flush=True)

# Save updated weights
with open(weights_path, "w") as f:
    json.dump(ensemble.weights, f, indent=2)
print(f"  Weights saved to {weights_path}", flush=True)

print("\n" + "=" * 60, flush=True)
print("DONE", flush=True)
print("=" * 60, flush=True)
