"""Feature store for offline (parquet) and online (Redis) feature serving."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


class FeatureStore:
    """Dual-mode feature store: offline parquet files and online Redis cache."""

    def __init__(self, offline_path: Path, redis_client=None):
        self.offline_path = offline_path
        self.offline_path.mkdir(parents=True, exist_ok=True)
        self.redis = redis_client

    def save_offline(self, features: pd.DataFrame, version: str = "latest") -> Path:
        path = self.offline_path / f"features_v{version}.parquet"
        features.to_parquet(path, index=True)
        return path

    def load_offline(self, version: str = "latest") -> pd.DataFrame:
        path = self.offline_path / f"features_v{version}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Feature file not found: {path}")
        return pd.read_parquet(path)

    def cache_online(self, borrower_id: str, features: dict, ttl: int = 3600):
        if self.redis:
            self.redis.setex(
                f"features:{borrower_id}",
                ttl,
                json.dumps(features, default=str),
            )

    def get_online(self, borrower_id: str) -> dict | None:
        if self.redis:
            data = self.redis.get(f"features:{borrower_id}")
            if data:
                return json.loads(data)
        return None

    def get_feature_metadata(self, version: str = "latest") -> dict:
        try:
            df = self.load_offline(version)
            return {
                "n_features": len(df.columns),
                "n_rows": len(df),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            }
        except FileNotFoundError:
            return {}
