"""Download and preprocess Kaggle credit datasets."""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Standard column schema that all data sources map to
STANDARD_COLUMNS = [
    "borrower_id",
    "age",
    "annual_income",
    "employment_length_years",
    "employment_type",
    "home_ownership",
    "existing_credit_lines",
    "total_credit_limit",
    "current_credit_balance",
    "credit_utilization_ratio",
    "months_since_last_delinquency",
    "number_of_delinquencies",
    "debt_to_income_ratio",
    "requested_loan_amount",
    "loan_purpose",
    "state",
    "account_age_months",
    "profile_completeness_score",
    "device_type",
    "is_default",
    "is_fraud",
    "lgd_value",
    "ead_value",
]


class DataDownloader:
    """Download and standardize credit datasets from Kaggle or bundled CSV."""

    def __init__(self, output_dir: Path, seed: int = 42):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.rng = np.random.default_rng(seed)

    def download_and_preprocess(self) -> pd.DataFrame:
        """Try to load data from local CSV or Kaggle. Falls back to synthetic."""
        # Try loading Give Me Some Credit format (most portable, included in many repos)
        local_path = self.output_dir / "raw" / "cs-training.csv"
        if local_path.exists():
            logger.info("Loading local Give Me Some Credit dataset from %s", local_path)
            return self._preprocess_give_me_some_credit(pd.read_csv(local_path))

        # Try kaggle CLI download
        try:
            return self._try_kaggle_download()
        except Exception as e:
            logger.warning("Kaggle download failed: %s. Falling back to synthetic data.", e)
            return pd.DataFrame()

    def _try_kaggle_download(self) -> pd.DataFrame:
        """Attempt to download via kaggle CLI."""
        import subprocess

        raw_dir = self.output_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [
                "kaggle",
                "competitions",
                "download",
                "-c",
                "GiveMeSomeCredit",
                "-p",
                str(raw_dir),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"kaggle CLI failed: {result.stderr}")

        zip_path = raw_dir / "GiveMeSomeCredit.zip"
        if zip_path.exists():
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(raw_dir)

        csv_path = raw_dir / "cs-training.csv"
        if csv_path.exists():
            return self._preprocess_give_me_some_credit(pd.read_csv(csv_path))

        raise FileNotFoundError("Could not find cs-training.csv after extraction")

    def _preprocess_give_me_some_credit(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize Give Me Some Credit dataset to our schema."""
        n = len(df)

        # Map columns
        result = pd.DataFrame()
        result["borrower_id"] = [f"gmc-{i:06d}" for i in range(n)]
        result["age"] = df.get("age", self.rng.integers(22, 70, size=n)).astype(int)
        result["annual_income"] = df.get("MonthlyIncome", pd.Series(self.rng.lognormal(10.5, 0.5, n))).fillna(4500) * 12
        result["employment_length_years"] = self.rng.exponential(5.0, n).clip(0, 40).round(1)

        emp_types = ["employed", "self_employed", "unemployed", "retired"]
        result["employment_type"] = self.rng.choice(emp_types, n, p=[0.65, 0.15, 0.10, 0.10])

        home_types = ["own", "mortgage", "rent"]
        result["home_ownership"] = self.rng.choice(home_types, n, p=[0.20, 0.40, 0.40])

        result["existing_credit_lines"] = (
            df.get(
                "NumberOfOpenCreditLinesAndLoans",
                pd.Series(self.rng.poisson(8, n)),
            )
            .fillna(5)
            .astype(int)
        )

        result["total_credit_limit"] = (result["annual_income"] * self.rng.uniform(0.3, 1.5, n)).round(2)
        result["current_credit_balance"] = (result["total_credit_limit"] * self.rng.beta(2, 5, n)).round(2)

        result["credit_utilization_ratio"] = (
            df.get(
                "RevolvingUtilizationOfUnsecuredLines",
                pd.Series(result["current_credit_balance"] / result["total_credit_limit"].clip(1)),
            )
            .fillna(0.5)
            .clip(0, 2.0)
        )

        n30 = df.get("NumberOfTime30-59DaysPastDueNotWorse", pd.Series(np.zeros(n))).fillna(0)
        n60 = df.get("NumberOfTime60-89DaysPastDueNotWorse", pd.Series(np.zeros(n))).fillna(0)
        n90 = df.get("NumberOfTimes90DaysLate", pd.Series(np.zeros(n))).fillna(0)
        total_delinq = (n30 + n60 + n90).astype(int)
        result["number_of_delinquencies"] = total_delinq

        has_delinq = total_delinq > 0
        months_since = pd.Series(np.nan, index=range(n))
        months_since[has_delinq] = self.rng.integers(1, 60, size=has_delinq.sum())
        result["months_since_last_delinquency"] = months_since

        result["debt_to_income_ratio"] = (
            df.get("DebtRatio", pd.Series(self.rng.uniform(0.05, 0.8, n))).fillna(0.3).clip(0, 5.0)
        )

        result["requested_loan_amount"] = (result["annual_income"] * self.rng.uniform(0.1, 0.5, n)).round(2)

        purposes = [
            "debt_consolidation",
            "home_improvement",
            "business",
            "education",
            "personal",
        ]
        result["loan_purpose"] = self.rng.choice(purposes, n, p=[0.40, 0.15, 0.15, 0.10, 0.20])

        states = [
            "CA",
            "TX",
            "FL",
            "NY",
            "PA",
            "IL",
            "OH",
            "GA",
            "NC",
            "MI",
            "NJ",
            "VA",
            "WA",
            "AZ",
            "MA",
            "TN",
            "IN",
            "MO",
            "MD",
            "WI",
        ]
        result["state"] = self.rng.choice(states, n)
        result["account_age_months"] = self.rng.integers(6, 180, size=n)
        result["profile_completeness_score"] = self.rng.uniform(0.6, 1.0, n).round(2)
        result["device_type"] = self.rng.choice(["mobile", "desktop", "tablet"], n, p=[0.55, 0.35, 0.10])

        # Target variable
        result["is_default"] = (
            df.get("SeriousDlqin2yrs", pd.Series(self.rng.binomial(1, 0.08, n))).fillna(0).astype(int)
        )

        # Fraud is synthetic
        result["is_fraud"] = self.rng.binomial(1, 0.015, n).astype(int)

        # LGD for defaulters
        lgd = np.zeros(n)
        default_mask = result["is_default"] == 1
        lgd[default_mask] = self.rng.beta(2, 5, default_mask.sum())
        result["lgd_value"] = lgd.round(4)

        # EAD
        drawn = result["current_credit_balance"].values
        limit = result["total_credit_limit"].values
        ccf = self.rng.beta(2, 8, n)
        ead = drawn + ccf * np.maximum(limit - drawn, 0)
        ead = np.clip(ead, drawn, limit)
        result["ead_value"] = ead.round(2)

        return result

    def _preprocess_lending_club(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize Lending Club dataset to our schema."""
        n = len(df)
        result = pd.DataFrame()
        result["borrower_id"] = [f"lc-{i:06d}" for i in range(n)]

        # Lending Club has different column names
        result["annual_income"] = df.get("annual_inc", pd.Series(self.rng.lognormal(10.8, 0.6, n))).fillna(60000)
        result["age"] = self.rng.integers(22, 70, size=n)

        emp_length = df.get("emp_length", pd.Series(dtype=str))
        emp_years = emp_length.str.extract(r"(\d+)").astype(float).fillna(3.0)
        result["employment_length_years"] = emp_years.values.flatten().clip(0, 40)
        result["employment_type"] = self.rng.choice(
            ["employed", "self_employed", "unemployed", "retired"],
            n,
            p=[0.70, 0.15, 0.05, 0.10],
        )

        home_map = {"MORTGAGE": "mortgage", "RENT": "rent", "OWN": "own"}
        result["home_ownership"] = df.get("home_ownership", pd.Series(dtype=str)).map(home_map).fillna("rent")

        result["existing_credit_lines"] = df.get("open_acc", pd.Series(self.rng.poisson(8, n))).fillna(8).astype(int)
        result["total_credit_limit"] = df.get("total_rev_hi_lim", pd.Series(self.rng.lognormal(10, 0.8, n))).fillna(
            30000
        )
        result["current_credit_balance"] = df.get("revol_bal", pd.Series(self.rng.lognormal(9, 1.0, n))).fillna(10000)
        result["credit_utilization_ratio"] = (df.get("revol_util", pd.Series(dtype=float)).fillna(50.0) / 100.0).clip(
            0, 2.0
        )

        result["months_since_last_delinquency"] = df.get("mths_since_last_delinq", pd.Series(np.nan))
        result["number_of_delinquencies"] = df.get("delinq_2yrs", pd.Series(np.zeros(n))).fillna(0).astype(int)
        dti_raw = df.get("dti", pd.Series(self.rng.uniform(5, 30, n))).fillna(15.0)
        result["debt_to_income_ratio"] = (dti_raw / 100.0).clip(0, 5.0)
        result["requested_loan_amount"] = df.get("loan_amnt", pd.Series(self.rng.lognormal(9.5, 0.8, n))).fillna(15000)

        purpose_map = {
            "debt_consolidation": "debt_consolidation",
            "credit_card": "debt_consolidation",
            "home_improvement": "home_improvement",
            "small_business": "business",
            "educational": "education",
        }
        result["loan_purpose"] = df.get("purpose", pd.Series(dtype=str)).map(purpose_map).fillna("personal")

        result["state"] = df.get("addr_state", pd.Series(self.rng.choice(["CA", "TX", "FL", "NY"], n)))
        result["account_age_months"] = self.rng.integers(6, 180, size=n)
        result["profile_completeness_score"] = self.rng.uniform(0.6, 1.0, n).round(2)
        result["device_type"] = self.rng.choice(["mobile", "desktop", "tablet"], n, p=[0.55, 0.35, 0.10])

        status_default = {"Charged Off", "Default", "Late (31-120 days)"}
        result["is_default"] = df.get("loan_status", pd.Series(dtype=str)).isin(status_default).astype(int)
        result["is_fraud"] = self.rng.binomial(1, 0.015, n).astype(int)

        lgd = np.zeros(n)
        default_mask = result["is_default"] == 1
        lgd[default_mask] = self.rng.beta(2, 5, default_mask.sum())
        result["lgd_value"] = lgd.round(4)

        drawn = result["current_credit_balance"].values.astype(float)
        limit = result["total_credit_limit"].values.astype(float)
        ccf = self.rng.beta(2, 8, n)
        ead = drawn + ccf * np.maximum(limit - drawn, 0)
        ead = np.clip(ead, drawn, limit)
        result["ead_value"] = ead.round(2)

        return result
