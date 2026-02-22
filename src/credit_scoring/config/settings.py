from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class DatabaseSettings(BaseSettings):
    url: str = "postgresql://credit:credit@localhost:5432/credit_scoring"
    pool_size: int = 10
    echo: bool = False


class RedisSettings(BaseSettings):
    url: str = "redis://localhost:6379/0"
    ttl_seconds: int = 3600


class DataSettings(BaseSettings):
    n_borrowers: int = 50000
    default_rate: float = 0.08
    fraud_rate: float = 0.015
    stress_scenario_fraction: float = 0.05
    transaction_months: int = 24
    avg_transactions_per_month: int = 15
    random_seed: int = 42
    output_dir: Path = PROJECT_ROOT / "data"
    kaggle_lending_club_url: str = "https://www.kaggle.com/datasets/adarshsng/lending-club-loan-data-csv"
    kaggle_give_me_credit_url: str = "https://www.kaggle.com/c/GiveMeSomeCredit"


class ModelSettings(BaseSettings):
    pd_model_type: str = "xgboost"
    lgd_model_type: str = "xgboost"
    ead_model_type: str = "xgboost"
    fraud_model_type: str = "lightgbm"
    deep_model_enabled: bool = True
    n_optuna_trials: int = 50
    cv_folds: int = 5
    min_auc_threshold: float = 0.70
    test_size: float = 0.20
    validation_size: float = 0.15
    models_dir: Path = PROJECT_ROOT / "models"


class DeepModelSettings(BaseSettings):
    embedding_dim: int = 32
    dense_layers: list[int] = Field(default=[256, 128, 64])
    dropout_rate: float = 0.3
    learning_rate: float = 0.001
    batch_size: int = 256
    epochs: int = 100
    early_stopping_patience: int = 15


class ServingSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    api_key: str = "dev-api-key-change-in-production"
    rate_limit_per_minute: int = 100
    workers: int = 4


class MonitoringSettings(BaseSettings):
    psi_threshold: float = 0.25
    psi_warning_threshold: float = 0.10
    drift_check_interval_hours: int = 24


class Settings(BaseSettings):
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    data: DataSettings = Field(default_factory=DataSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    deep_model: DeepModelSettings = Field(default_factory=DeepModelSettings)
    serving: ServingSettings = Field(default_factory=ServingSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    log_level: str = "INFO"
    mlflow_tracking_uri: str = "http://localhost:5000"


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings(config_dir: Path | None = None) -> Settings:
    """Load settings from YAML config files, then override with environment variables."""
    if config_dir is None:
        config_dir = PROJECT_ROOT / "configs"

    merged: dict[str, Any] = {}
    for config_file in ["data.yaml", "model.yaml", "serving.yaml"]:
        path = config_dir / config_file
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
                if data:
                    merged = _deep_merge(merged, data)

    settings_kwargs: dict[str, Any] = {}

    if "data" in merged:
        settings_kwargs["data"] = DataSettings(**merged["data"])
    if "model" in merged:
        settings_kwargs["model"] = ModelSettings(**merged["model"])
    if "deep_model" in merged:
        settings_kwargs["deep_model"] = DeepModelSettings(**merged["deep_model"])
    if "serving" in merged:
        settings_kwargs["serving"] = ServingSettings(**merged["serving"])
    if "monitoring" in merged:
        settings_kwargs["monitoring"] = MonitoringSettings(**merged["monitoring"])

    return Settings(**settings_kwargs)
