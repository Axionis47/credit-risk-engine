"""FastAPI application factory."""

from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from credit_scoring.config.settings import load_settings
from credit_scoring.features.engineering import FeatureEngineer
from credit_scoring.models.ensemble import CreditScoreCalculator, PDEnsemble
from credit_scoring.serving.middleware import setup_middleware
from credit_scoring.serving.routes import ab_testing, explanation, monitoring, scoring


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models and resources on startup, clean up on shutdown."""
    settings = load_settings()
    app.state.settings = settings
    app.state.start_time = time.monotonic()
    app.state.request_count = 0
    app.state.total_latency_ms = 0.0
    app.state.error_count = 0
    app.state.model_metrics = {}

    models_dir = settings.model.models_dir

    # Load PD models
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

    # TensorFlow model
    if (models_dir / "tf_pd_model").exists():
        try:
            from credit_scoring.models.deep_model import TensorFlowPDModel
            tf_model = TensorFlowPDModel.load(models_dir / "tf_pd_model")
            pd_models["tensorflow"] = tf_model
        except Exception as e:
            print(f"Warning: Could not load TF model: {e}")

    # Build ensemble
    ensemble = PDEnsemble(pd_models)
    weights_path = models_dir / "ensemble_weights.json"
    if weights_path.exists():
        with open(weights_path) as f:
            saved_weights = json.load(f)
            # Only use weights for models we loaded
            ensemble.weights = {
                k: v for k, v in saved_weights.items() if k in pd_models
            }
            # Normalize
            total = sum(ensemble.weights.values())
            if total > 0:
                ensemble.weights = {k: v / total for k, v in ensemble.weights.items()}

    # Load LGD, EAD, Fraud
    from credit_scoring.models.ead_model import EADModel
    from credit_scoring.models.fraud_model import FraudModel
    from credit_scoring.models.lgd_model import TwoStageLGDModel

    lgd_model = None
    ead_model = None
    fraud_model = None

    if (models_dir / "lgd_model.joblib").exists():
        lgd_model = TwoStageLGDModel.load(models_dir / "lgd_model.joblib")
    if (models_dir / "ead_model.joblib").exists():
        ead_model = EADModel.load(models_dir / "ead_model.joblib")
    if (models_dir / "fraud_model.joblib").exists():
        fraud_model = FraudModel.load(models_dir / "fraud_model.joblib")

    # Build scorer
    if lgd_model and ead_model and fraud_model:
        app.state.scorer = CreditScoreCalculator(
            ensemble, lgd_model, ead_model, fraud_model,
        )
    else:
        app.state.scorer = None

    # Feature engineer
    app.state.feature_engineer = FeatureEngineer()

    # Load trained feature names from any PD model for single-scoring alignment
    for model in pd_models.values():
        if hasattr(model, 'pipeline') and hasattr(model.pipeline, 'feature_names_in_'):
            app.state.feature_engineer.trained_feature_names = list(model.pipeline.feature_names_in_)
            break

    # SHAP explainer
    app.state.shap_explainer = None
    app.state.adverse_action = None
    background_path = models_dir / "shap_background.parquet"
    if background_path.exists() and "xgboost" in pd_models:
        try:
            import pandas as pd
            from credit_scoring.explainability.adverse_action import AdverseActionGenerator
            from credit_scoring.explainability.shap_explainer import SHAPExplainer

            background = pd.read_parquet(background_path)
            app.state.shap_explainer = SHAPExplainer(pd_models["xgboost"], background)
            app.state.adverse_action = AdverseActionGenerator(app.state.shap_explainer)
        except Exception as e:
            print(f"Warning: Could not initialize SHAP: {e}")

    # Shadow mode: champion=ensemble, challenger=xgboost-only
    app.state.shadow_router = None
    if app.state.scorer and "xgboost" in pd_models:
        try:
            from credit_scoring.serving.shadow_mode import ShadowModeRouter

            challenger_ensemble = PDEnsemble({"xgboost": pd_models["xgboost"]})
            challenger_scorer = CreditScoreCalculator(
                challenger_ensemble, lgd_model, ead_model, fraud_model,
            )
            app.state.shadow_router = ShadowModeRouter(
                champion_scorer=app.state.scorer,
                challenger_scorer=challenger_scorer,
                shadow_traffic_pct=1.0,  # Shadow 100% of requests for demo
            )
            print("Shadow mode enabled: ensemble (champion) vs xgboost-only (challenger)")
        except Exception as e:
            print(f"Warning: Could not initialize shadow mode: {e}")

    # Redis
    app.state.redis = None
    try:
        import redis
        app.state.redis = redis.from_url(settings.redis.url)
        app.state.redis.ping()
    except Exception:
        pass

    print("API started. Models loaded.")
    yield

    # Cleanup
    if app.state.redis:
        try:
            app.state.redis.close()
        except Exception:
            pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="Credit Scoring API",
        description="Production credit scoring with PD, LGD, EAD models",
        version="1.0.0",
        lifespan=lifespan,
    )

    setup_middleware(app)
    app.include_router(scoring.router, prefix="/api/v1")
    app.include_router(explanation.router, prefix="/api/v1")
    app.include_router(monitoring.router, prefix="/api/v1")
    app.include_router(ab_testing.router, prefix="/api/v1")

    return app
