"""Unified data loading for both Kaggle and synthetic data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class DataLoader:
    """Load datasets from parquet files."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    def load_borrowers(self) -> pd.DataFrame:
        path = self.data_dir / "borrowers.parquet"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found. Run 'make generate-data' or 'make download-data' first.")
        return pd.read_parquet(path)

    def load_transactions(self) -> pd.DataFrame:
        path = self.data_dir / "transactions.parquet"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found. Run 'make generate-data' first.")
        return pd.read_parquet(path)

    def load_payments(self) -> pd.DataFrame:
        path = self.data_dir / "payments.parquet"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found. Run 'make generate-data' first.")
        return pd.read_parquet(path)

    def load_all(self) -> dict[str, pd.DataFrame]:
        return {
            "borrowers": self.load_borrowers(),
            "transactions": self.load_transactions(),
            "payments": self.load_payments(),
        }
