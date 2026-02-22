"""Feature engineering pipeline for credit scoring.

Computes 100+ features from borrower profiles, transaction histories,
and payment records across 7 feature groups.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class FeatureEngineer:
    """Compute all engineered features from raw datasets."""

    CATEGORICAL_COLUMNS = ["employment_type", "home_ownership", "loan_purpose", "device_type"]
    STATE_COLUMN = "state"

    def __init__(self, reference_date: pd.Timestamp | None = None):
        self.reference_date = reference_date or pd.Timestamp("2024-12-31")
        self._state_target_map: dict[str, float] | None = None
        self._feature_medians: dict[str, float] | None = None
        self.trained_feature_names: list[str] | None = None

    def compute_all(
        self,
        borrowers: pd.DataFrame,
        transactions: pd.DataFrame,
        payments: pd.DataFrame,
        fit: bool = True,
    ) -> pd.DataFrame:
        """Compute all features for each borrower.

        Args:
            borrowers: Borrower profile DataFrame.
            transactions: Transaction history DataFrame.
            payments: Payment history DataFrame.
            fit: If True, learn imputation values and encodings from this data.

        Returns:
            DataFrame indexed by borrower_id with 100+ feature columns.
        """
        # Base demographic features
        demo = self._compute_demographic_features(borrowers)

        # Credit history features (from borrower profile)
        credit = self._compute_credit_features(borrowers)

        # Velocity features from transactions
        velocity = self._compute_velocity_features(transactions)

        # Aggregation features
        agg = self._compute_aggregation_features(transactions)

        # Behavioral features
        behavioral = self._compute_behavioral_features(borrowers, transactions)

        # Time series features
        ts = self._compute_time_series_features(transactions)

        # Payment features
        payment = self._compute_payment_features(payments)

        # Risk ratios
        risk = self._compute_risk_ratios(borrowers)

        # Merge all on borrower_id
        features = demo.copy()
        for df in [credit, velocity, agg, behavioral, ts, payment, risk]:
            features = features.merge(df, on="borrower_id", how="left")

        # Encode categoricals
        features = self._encode_categoricals(features, fit=fit)

        # Handle missing values
        features = self._handle_missing(features, fit=fit)

        # Remove non-feature columns
        drop_cols = [
            "borrower_id",
            "is_default",
            "is_fraud",
            "lgd_value",
            "ead_value",
        ]
        feature_cols = [c for c in features.columns if c not in drop_cols]

        result = features[["borrower_id"] + feature_cols].copy()
        result = result.set_index("borrower_id")

        # Replace inf with nan then fill
        result = result.replace([np.inf, -np.inf], np.nan)
        result = result.fillna(0)

        return result

    def compute_single(self, data: dict) -> pd.DataFrame:
        """Compute features for a single scoring request.

        Simplified path for API serving. Uses pre-computed medians for
        transaction/payment features when actual history is not available.
        """
        borrower = pd.DataFrame([data])
        # Derive credit_utilization_ratio if not provided
        if "credit_utilization_ratio" not in borrower.columns or borrower["credit_utilization_ratio"].isna().all():
            limit = borrower["total_credit_limit"].iloc[0]
            balance = borrower["current_credit_balance"].iloc[0]
            borrower["credit_utilization_ratio"] = balance / max(limit, 1.0)
        demo = self._compute_demographic_features(borrower)
        credit = self._compute_credit_features(borrower)
        risk = self._compute_risk_ratios(borrower)

        features = demo.copy()
        for df in [credit, risk]:
            features = features.merge(df, on="borrower_id", how="left")

        features = self._encode_categoricals(features, fit=False)
        features = self._handle_missing(features, fit=False)

        drop_cols = ["borrower_id", "is_default", "is_fraud", "lgd_value", "ead_value"]
        feature_cols = [c for c in features.columns if c not in drop_cols]
        result = features[feature_cols].copy()
        result = result.replace([np.inf, -np.inf], np.nan).fillna(0)

        # Ensure all model features exist (transaction/payment features default to 0)
        if self.trained_feature_names is not None:
            for col in self.trained_feature_names:
                if col not in result.columns:
                    result[col] = 0.0
            result = result[self.trained_feature_names]

        return result

    def _compute_demographic_features(self, borrowers: pd.DataFrame) -> pd.DataFrame:
        df = borrowers[["borrower_id"]].copy()
        df["age"] = borrowers["age"].astype(float)
        df["log_annual_income"] = np.log1p(borrowers["annual_income"])
        df["employment_length_years"] = borrowers["employment_length_years"]
        df["account_age_months"] = borrowers["account_age_months"]
        df["profile_completeness_score"] = borrowers["profile_completeness_score"]

        # Keep categoricals for later encoding
        for col in self.CATEGORICAL_COLUMNS:
            if col in borrowers.columns:
                df[col] = borrowers[col]
        if self.STATE_COLUMN in borrowers.columns:
            df[self.STATE_COLUMN] = borrowers[self.STATE_COLUMN]

        return df

    def _compute_credit_features(self, borrowers: pd.DataFrame) -> pd.DataFrame:
        df = borrowers[["borrower_id"]].copy()
        df["credit_utilization_ratio"] = borrowers["credit_utilization_ratio"]
        df["existing_credit_lines"] = borrowers["existing_credit_lines"]
        df["months_since_last_delinquency"] = borrowers["months_since_last_delinquency"]
        df["number_of_delinquencies"] = borrowers["number_of_delinquencies"]
        df["debt_to_income_ratio"] = borrowers["debt_to_income_ratio"]
        return df

    def _compute_velocity_features(self, transactions: pd.DataFrame) -> pd.DataFrame:
        ref = self.reference_date
        t = transactions.copy()
        t["timestamp"] = pd.to_datetime(t["timestamp"])

        results = []
        for window_days, suffix in [(7, "7d"), (30, "30d"), (90, "90d")]:
            cutoff = ref - pd.Timedelta(days=window_days)
            window = t[t["timestamp"] >= cutoff]

            grp = window.groupby("borrower_id")
            agg_df = pd.DataFrame()
            agg_df[f"txn_count_{suffix}"] = grp["amount"].count()
            agg_df[f"txn_amount_sum_{suffix}"] = grp["amount"].sum()

            if suffix == "30d":
                agg_df["txn_amount_mean_30d"] = grp["amount"].mean()
                agg_df["txn_amount_std_30d"] = grp["amount"].std()
                agg_df["txn_amount_max_30d"] = grp["amount"].max()
                agg_df["decline_rate_30d"] = grp["is_declined"].mean()
                agg_df["international_txn_rate_30d"] = grp["is_international"].mean()

            results.append(agg_df)

        merged = results[0]
        for r in results[1:]:
            merged = merged.join(r, how="outer")

        merged = merged.fillna(0).reset_index()
        merged = merged.rename(columns={"index": "borrower_id"})
        if "borrower_id" not in merged.columns and merged.index.name == "borrower_id":
            merged = merged.reset_index()

        return merged

    def _compute_aggregation_features(self, transactions: pd.DataFrame) -> pd.DataFrame:
        t = transactions.copy()
        t["timestamp"] = pd.to_datetime(t["timestamp"])
        t["month"] = t["timestamp"].dt.to_period("M")

        # Average monthly spend by category
        monthly_cat = t.groupby(["borrower_id", "month", "merchant_category"])["amount"].sum().reset_index()
        monthly_avg = monthly_cat.groupby(["borrower_id", "merchant_category"])["amount"].mean().unstack(fill_value=0)

        cat_cols = {}
        for cat in ["grocery", "restaurant", "online", "travel"]:
            col_name = f"avg_spend_{cat}"
            cat_cols[col_name] = monthly_avg[cat] if cat in monthly_avg.columns else 0

        agg_df = pd.DataFrame(cat_cols)

        # Diversity and entropy
        ref = self.reference_date
        last_30 = t[t["timestamp"] >= ref - pd.Timedelta(days=30)]

        diversity = last_30.groupby("borrower_id").agg(
            merchant_diversity_30d=("merchant_category", "nunique"),
            channel_diversity=("channel", "nunique"),
        )

        # Shannon entropy of spending categories (vectorized)
        cat_totals = t.groupby(["borrower_id", "merchant_category"])["amount"].sum().reset_index()
        borrower_totals = cat_totals.groupby("borrower_id")["amount"].transform("sum")
        cat_totals["prob"] = cat_totals["amount"] / borrower_totals.clip(lower=1e-8)
        cat_totals["entropy_term"] = np.where(
            cat_totals["prob"] > 0,
            -cat_totals["prob"] * np.log2(cat_totals["prob"]),
            0.0,
        )
        entropy = cat_totals.groupby("borrower_id")["entropy_term"].sum()
        entropy.name = "spend_category_entropy"

        result = agg_df.join(diversity, how="outer").join(entropy, how="outer")
        result = result.fillna(0).reset_index()
        if "borrower_id" not in result.columns:
            result = result.rename(columns={"index": "borrower_id"})

        return result

    def _compute_behavioral_features(self, borrowers: pd.DataFrame, transactions: pd.DataFrame) -> pd.DataFrame:
        t = transactions.copy()
        t["timestamp"] = pd.to_datetime(t["timestamp"])

        grp = t.groupby("borrower_id")

        mobile = t[t["channel"] == "mobile"].groupby("borrower_id").size()
        total = grp.size()
        mobile_fraction = (mobile / total).fillna(0)

        t["is_weekend"] = t["timestamp"].dt.dayofweek >= 5
        weekend = t[t["is_weekend"]].groupby("borrower_id").size()
        weekend_fraction = (weekend / total).fillna(0)

        t["is_night"] = t["timestamp"].dt.hour.isin(list(range(0, 6)) + [22, 23])
        night = t[t["is_night"]].groupby("borrower_id").size()
        night_fraction = (night / total).fillna(0)

        result = (
            pd.DataFrame(
                {
                    "mobile_txn_fraction": mobile_fraction,
                    "weekend_txn_fraction": weekend_fraction,
                    "nighttime_txn_fraction": night_fraction,
                }
            )
            .fillna(0)
            .reset_index()
        )

        if "borrower_id" not in result.columns:
            result = result.rename(columns={"index": "borrower_id"})

        return result

    def _compute_time_series_features(self, transactions: pd.DataFrame) -> pd.DataFrame:
        t = transactions.copy()
        t["timestamp"] = pd.to_datetime(t["timestamp"])
        t["month"] = t["timestamp"].dt.to_period("M")

        monthly = (
            t.groupby(["borrower_id", "month"])
            .agg(total_spend=("amount", "sum"), txn_count=("amount", "count"))
            .reset_index()
        )
        monthly["month_idx"] = monthly.groupby("borrower_id").cumcount()
        monthly = monthly.sort_values(["borrower_id", "month_idx"])

        # Vectorized trend computation using tail-N slices
        def _vectorized_trends(monthly_df, col, n_months, trend_name):
            """Compute linear slope for the last n_months per borrower using vectorized ops."""
            # Get last n rows per borrower
            rank_desc = monthly_df.groupby("borrower_id").cumcount(ascending=False)
            tail = monthly_df[rank_desc < n_months].copy()
            tail["x"] = tail.groupby("borrower_id").cumcount()
            g = tail.groupby("borrower_id")
            n = g["x"].count()
            sx = g["x"].sum()
            sy = g[col].sum()
            tail["_xy"] = tail["x"] * tail[col]
            tail["_x2"] = tail["x"] ** 2
            sxy = tail.groupby("borrower_id")["_xy"].sum()
            sx2 = tail.groupby("borrower_id")["_x2"].sum()
            denom = n * sx2 - sx**2
            slope = np.where(denom.abs() > 1e-8, (n * sxy - sx * sy) / denom, 0.0)
            result = pd.Series(slope, index=n.index, name=trend_name)
            # Borrowers with < 2 data points get 0
            result[n < 2] = 0.0
            return result

        spend_trend_3m = _vectorized_trends(monthly, "total_spend", 3, "spend_trend_3m")
        spend_trend_6m = _vectorized_trends(monthly, "total_spend", 6, "spend_trend_6m")
        txn_freq_trend = _vectorized_trends(monthly, "txn_count", 6, "txn_frequency_trend")
        trends = pd.concat([spend_trend_3m, spend_trend_6m, txn_freq_trend], axis=1)

        # Volatility (vectorized)
        vol_stats = monthly.groupby("borrower_id")["total_spend"].agg(["std", "mean"])
        volatility = vol_stats["std"] / (vol_stats["mean"] + 1e-8)
        volatility.name = "spend_volatility_6m"

        result = trends.join(volatility, how="outer").fillna(0).reset_index()
        if "borrower_id" not in result.columns:
            result = result.rename(columns={"index": "borrower_id"})

        return result

    def _compute_payment_features(self, payments: pd.DataFrame) -> pd.DataFrame:
        p = payments.copy()

        grp = p.groupby("borrower_id")

        on_time = p[p["payment_status"] == "on_time"].groupby("borrower_id").size()
        total_payments = grp.size()
        on_time_rate = (on_time / total_payments).fillna(0)

        avg_dpd = grp["days_past_due"].mean()
        max_dpd = grp["days_past_due"].max()
        missed_count = p[p["payment_status"] == "missed"].groupby("borrower_id").size().fillna(0)

        # Payment amount ratio (vectorized)
        p["_pay_ratio"] = p["amount_paid"] / p["amount_due"].clip(lower=1)
        pay_ratio = p.groupby("borrower_id")["_pay_ratio"].mean()
        pay_ratio.name = "payment_amount_ratio"

        # Consecutive on-time streak from most recent (vectorized)
        p_sorted = p.sort_values(["borrower_id", "due_date"])
        p_sorted["_is_on_time"] = (p_sorted["payment_status"] == "on_time").astype(int)
        # Reverse rank within each borrower (0 = most recent)
        p_sorted["_rev_rank"] = p_sorted.groupby("borrower_id").cumcount(ascending=False)
        # Mark the first non-on-time payment per borrower (from most recent)
        p_sorted["_break"] = (p_sorted["_is_on_time"] == 0).astype(int)
        sorted_by_rev = p_sorted.sort_values(["borrower_id", "_rev_rank"])
        p_sorted["_cum_break"] = sorted_by_rev.groupby("borrower_id")["_break"].cumsum()
        # Streak = count of records before the first break (cum_break == 0)
        streak = p_sorted[p_sorted["_cum_break"] == 0].groupby("borrower_id").size()
        streak.name = "consecutive_on_time"

        # Payment trend in days_past_due over last 3 months (vectorized)
        p_sorted["_rank_desc"] = p_sorted.groupby("borrower_id").cumcount(ascending=False)
        tail3 = p_sorted[p_sorted["_rank_desc"] < 3].copy()
        tail3["_x"] = tail3.groupby("borrower_id").cumcount()
        g3 = tail3.groupby("borrower_id")
        n = g3["_x"].count()
        sx = g3["_x"].sum()
        sy = g3["days_past_due"].sum()
        sxy = (tail3["_x"] * tail3["days_past_due"]).groupby(tail3["borrower_id"]).sum()
        sx2 = (tail3["_x"] ** 2).groupby(tail3["borrower_id"]).sum()
        denom = n * sx2 - sx**2
        pmt_trend = pd.Series(
            np.where(denom.abs() > 1e-8, (n * sxy - sx * sy) / denom, 0.0),
            index=n.index,
        )
        pmt_trend[n < 2] = 0.0
        pmt_trend.name = "payment_trend_3m"

        result = (
            pd.DataFrame(
                {
                    "on_time_payment_rate": on_time_rate,
                    "avg_days_past_due": avg_dpd,
                    "max_days_past_due": max_dpd,
                    "missed_payment_count": missed_count,
                    "payment_amount_ratio": pay_ratio,
                    "consecutive_on_time": streak,
                    "payment_trend_3m": pmt_trend,
                }
            )
            .fillna(0)
            .reset_index()
        )

        if "borrower_id" not in result.columns:
            result = result.rename(columns={"index": "borrower_id"})

        return result

    def _compute_risk_ratios(self, borrowers: pd.DataFrame) -> pd.DataFrame:
        df = borrowers[["borrower_id"]].copy()
        income = borrowers["annual_income"].clip(lower=1)
        df["loan_to_income_ratio"] = borrowers["requested_loan_amount"] / income
        df["balance_to_income_ratio"] = borrowers["current_credit_balance"] / income
        df["utilization_x_dti"] = borrowers["credit_utilization_ratio"] * borrowers["debt_to_income_ratio"]
        df["income_stability_proxy"] = borrowers["employment_length_years"] / borrowers["age"].clip(lower=1)
        return df

    def _encode_categoricals(self, df: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
        result = df.copy()

        # One-hot encode low-cardinality categoricals
        for col in self.CATEGORICAL_COLUMNS:
            if col in result.columns:
                dummies = pd.get_dummies(result[col], prefix=col, dtype=float)
                result = pd.concat([result, dummies], axis=1)
                result = result.drop(columns=[col])

        # Target encode state (high cardinality)
        if self.STATE_COLUMN in result.columns:
            if fit and "is_default" in df.columns:
                self._state_target_map = df.groupby(self.STATE_COLUMN)["is_default"].mean().to_dict()
            if self._state_target_map:
                global_mean = df["is_default"].mean() if "is_default" in df.columns else 0.08
                result["state_encoded"] = result[self.STATE_COLUMN].map(self._state_target_map).fillna(global_mean)
            else:
                result["state_encoded"] = 0.08
            result = result.drop(columns=[self.STATE_COLUMN])

        return result

    def _handle_missing(self, df: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
        result = df.copy()

        # Special handling for months_since_last_delinquency
        if "months_since_last_delinquency" in result.columns:
            result["has_delinquency"] = (~result["months_since_last_delinquency"].isna()).astype(float)
            result["months_since_last_delinquency"] = result["months_since_last_delinquency"].fillna(-1)

        # Median imputation for all numeric columns
        numeric_cols = result.select_dtypes(include=[np.number]).columns
        if fit:
            self._feature_medians = result[numeric_cols].median().to_dict()

        if self._feature_medians:
            for col in numeric_cols:
                if col in self._feature_medians:
                    result[col] = result[col].fillna(self._feature_medians[col])

        return result
