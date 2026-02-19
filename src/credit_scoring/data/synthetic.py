"""Synthetic data generation for credit scoring.

Generates borrower profiles (fallback when Kaggle data is unavailable),
transaction histories, and payment records.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from credit_scoring.config.settings import DataSettings


class BorrowerProfileGenerator:
    """Generate synthetic borrower profiles using Gaussian copula for correlated features."""

    def __init__(self, settings: DataSettings):
        self.n = settings.n_borrowers
        self.default_rate = settings.default_rate
        self.fraud_rate = settings.fraud_rate
        self.rng = np.random.default_rng(settings.random_seed)

    def generate(self) -> pd.DataFrame:
        n = self.n

        # Gaussian copula: correlated normals -> transform to target marginals
        corr = np.array([
            # age, income, emp_len, credit_lines, limit, balance, delinq, dti
            [1.00, 0.40, 0.50, 0.30, 0.35, 0.20, -0.10, -0.05],
            [0.40, 1.00, 0.35, 0.25, 0.60, 0.30, -0.20, -0.35],
            [0.50, 0.35, 1.00, 0.15, 0.20, 0.10, -0.15, -0.10],
            [0.30, 0.25, 0.15, 1.00, 0.40, 0.35, 0.10, 0.05],
            [0.35, 0.60, 0.20, 0.40, 1.00, 0.50, -0.10, -0.15],
            [0.20, 0.30, 0.10, 0.35, 0.50, 1.00, 0.15, 0.20],
            [-0.10, -0.20, -0.15, 0.10, -0.10, 0.15, 1.00, 0.30],
            [-0.05, -0.35, -0.10, 0.05, -0.15, 0.20, 0.30, 1.00],
        ])

        z = self.rng.multivariate_normal(np.zeros(8), corr, size=n)
        u = stats.norm.cdf(z)  # uniform marginals

        # Transform to target distributions
        age = stats.truncnorm.ppf(u[:, 0], a=(18 - 38) / 12, b=(80 - 38) / 12, loc=38, scale=12).astype(int)
        annual_income = np.exp(stats.norm.ppf(u[:, 1], loc=10.8, scale=0.6)).clip(12000, 500000).round(2)
        employment_length = stats.expon.ppf(u[:, 2], scale=5.0).clip(0, 40).round(1)
        existing_credit_lines = stats.poisson.ppf(u[:, 3], mu=8).clip(0, 50).astype(int)
        total_credit_limit = (annual_income * stats.beta.ppf(u[:, 4], 3, 2) * 1.5).clip(1000, 200000).round(2)
        current_credit_balance = (total_credit_limit * stats.beta.ppf(u[:, 5], 2, 5)).clip(0).round(2)
        number_of_delinquencies = stats.poisson.ppf(u[:, 6], mu=0.5).clip(0, 20).astype(int)
        debt_to_income_ratio = stats.beta.ppf(u[:, 7], 2, 5).clip(0.01, 5.0).round(4)

        credit_utilization_ratio = np.where(
            total_credit_limit > 0,
            current_credit_balance / total_credit_limit,
            0.0,
        ).clip(0, 2.0).round(4)

        # Categorical features
        emp_types = ["employed", "self_employed", "unemployed", "retired"]
        employment_type = self.rng.choice(emp_types, n, p=[0.65, 0.15, 0.10, 0.10])

        home_types = ["own", "mortgage", "rent"]
        income_rank = np.argsort(np.argsort(annual_income)) / n
        home_probs = np.column_stack([
            0.10 + 0.20 * income_rank,
            0.30 + 0.20 * income_rank,
            0.60 - 0.40 * income_rank,
        ])
        home_probs = home_probs / home_probs.sum(axis=1, keepdims=True)
        home_ownership = np.array([
            self.rng.choice(home_types, p=p) for p in home_probs
        ])

        purposes = ["debt_consolidation", "home_improvement", "business", "education", "personal"]
        loan_purpose = self.rng.choice(purposes, n, p=[0.40, 0.15, 0.15, 0.10, 0.20])

        states = [
            "CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA", "NC", "MI",
            "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI",
        ]
        state = self.rng.choice(states, n)

        requested_loan_amount = (annual_income * self.rng.uniform(0.1, 0.5, n)).round(2)
        account_age_months = self.rng.integers(6, 180, size=n)
        profile_completeness_score = self.rng.uniform(0.5, 1.0, n).round(2)
        device_type = self.rng.choice(["mobile", "desktop", "tablet"], n, p=[0.55, 0.35, 0.10])

        has_delinq = number_of_delinquencies > 0
        months_since_last_delinquency = np.full(n, np.nan)
        months_since_last_delinquency[has_delinq] = self.rng.integers(
            1, 60, size=has_delinq.sum()
        )

        # Default indicator from latent logistic model
        standardize = lambda x: (x - x.mean()) / (x.std() + 1e-8)
        logit = (
            -3.5
            + 0.8 * standardize(credit_utilization_ratio)
            + 0.6 * standardize(debt_to_income_ratio)
            - 0.5 * standardize(annual_income / 10000)
            + 0.4 * standardize(number_of_delinquencies.astype(float))
            - 0.3 * standardize(employment_length)
            + 0.2 * standardize(requested_loan_amount / 10000)
            + self.rng.normal(0, 0.5, n)
        )

        # Calibrate intercept to hit target default rate
        from scipy.optimize import brentq

        def default_rate_at_intercept(intercept):
            probs = 1 / (1 + np.exp(-(logit + intercept)))
            return probs.mean() - self.default_rate

        try:
            intercept_adj = brentq(default_rate_at_intercept, -5, 5)
        except ValueError:
            intercept_adj = 0.0

        default_probs = 1 / (1 + np.exp(-(logit + intercept_adj)))
        is_default = (self.rng.uniform(0, 1, n) < default_probs).astype(int)

        # Fraud indicator
        is_fraud = self.rng.binomial(1, self.fraud_rate, n).astype(int)

        # LGD for defaulters
        lgd_value = np.zeros(n)
        default_mask = is_default == 1
        lgd_value[default_mask] = self.rng.beta(2, 5, default_mask.sum())
        lgd_value = lgd_value.round(4)

        # EAD
        ccf = self.rng.beta(2, 8, n)
        ead_value = current_credit_balance + ccf * np.maximum(total_credit_limit - current_credit_balance, 0)
        ead_value = np.clip(ead_value, current_credit_balance, total_credit_limit).round(2)

        borrower_ids = [f"syn-{uuid.uuid4().hex[:8]}" for _ in range(n)]

        return pd.DataFrame({
            "borrower_id": borrower_ids,
            "age": age,
            "annual_income": annual_income,
            "employment_length_years": employment_length,
            "employment_type": employment_type,
            "home_ownership": home_ownership,
            "existing_credit_lines": existing_credit_lines,
            "total_credit_limit": total_credit_limit,
            "current_credit_balance": current_credit_balance,
            "credit_utilization_ratio": credit_utilization_ratio,
            "months_since_last_delinquency": months_since_last_delinquency,
            "number_of_delinquencies": number_of_delinquencies,
            "debt_to_income_ratio": debt_to_income_ratio,
            "requested_loan_amount": requested_loan_amount,
            "loan_purpose": loan_purpose,
            "state": state,
            "account_age_months": account_age_months,
            "profile_completeness_score": profile_completeness_score,
            "device_type": device_type,
            "is_default": is_default,
            "is_fraud": is_fraud,
            "lgd_value": lgd_value,
            "ead_value": ead_value,
        })


class TransactionGenerator:
    """Generate synthetic transaction time series per borrower."""

    def __init__(self, borrowers: pd.DataFrame, settings: DataSettings):
        self.borrowers = borrowers
        self.months = settings.transaction_months
        self.avg_txn_per_month = settings.avg_transactions_per_month
        self.rng = np.random.default_rng(settings.random_seed + 1)

    def generate(self) -> pd.DataFrame:
        all_txns = []
        categories = ["grocery", "restaurant", "gas", "online", "travel", "utilities", "entertainment"]
        cat_probs = [0.25, 0.15, 0.10, 0.25, 0.05, 0.10, 0.10]
        cat_avg_amounts = {"grocery": 45, "restaurant": 35, "gas": 40, "online": 60, "travel": 200, "utilities": 80, "entertainment": 30}
        channels = ["online", "in_store", "mobile"]

        n_borrowers = len(self.borrowers)
        end_date = pd.Timestamp("2024-12-31")
        start_date = end_date - pd.DateOffset(months=self.months)

        for idx, row in self.borrowers.iterrows():
            income_factor = row["annual_income"] / 60000
            is_fraud = row["is_fraud"] == 1

            # Spending variability based on credit risk features (not the label)
            dti = row.get("debt_to_income_ratio", 0.3)
            util = row.get("credit_utilization_ratio", 0.5)
            risk_factor = 1.0 + 0.3 * min(dti, 1.0) + 0.2 * min(util, 1.5)

            for month_offset in range(self.months):
                month_date = start_date + pd.DateOffset(months=month_offset)
                n_txns = max(1, self.rng.poisson(self.avg_txn_per_month * income_factor * 0.5))

                # Limit per-borrower transactions for performance
                n_txns = min(n_txns, 30)

                # Spending variation over time (independent of default label)
                spending_mult = risk_factor * (1.0 + 0.05 * self.rng.standard_normal())

                # Fraud burst in last 2 months
                fraud_burst = is_fraud and month_offset >= self.months - 2

                for _ in range(n_txns):
                    cat = self.rng.choice(categories, p=cat_probs)
                    base_amount = cat_avg_amounts[cat] * income_factor * spending_mult
                    amount = max(1.0, self.rng.lognormal(np.log(base_amount), 0.5))

                    day = self.rng.integers(1, 29)
                    hour = self.rng.integers(6, 23)
                    minute = self.rng.integers(0, 60)
                    ts = month_date.replace(day=day, hour=hour, minute=minute)

                    is_intl = self.rng.random() < (0.15 if fraud_burst else 0.03)
                    channel = self.rng.choice(channels, p=[0.40, 0.35, 0.25])
                    is_declined = self.rng.random() < (0.08 if fraud_burst else 0.02)
                    is_fraudulent = fraud_burst and self.rng.random() < 0.3

                    all_txns.append({
                        "transaction_id": f"txn-{uuid.uuid4().hex[:10]}",
                        "borrower_id": row["borrower_id"],
                        "timestamp": ts,
                        "amount": round(amount, 2),
                        "merchant_category": cat,
                        "is_international": is_intl,
                        "channel": channel,
                        "is_declined": is_declined,
                        "is_fraudulent": is_fraudulent,
                    })

            # Print progress every 5000 borrowers
            if (idx + 1) % 5000 == 0:
                print(f"  Generated transactions for {idx + 1}/{n_borrowers} borrowers")

        df = pd.DataFrame(all_txns)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df.sort_values(["borrower_id", "timestamp"]).reset_index(drop=True)


class PaymentHistoryGenerator:
    """Generate loan payment records per borrower."""

    def __init__(self, borrowers: pd.DataFrame, settings: DataSettings):
        self.borrowers = borrowers
        self.months = settings.transaction_months
        self.rng = np.random.default_rng(settings.random_seed + 2)

    def generate(self) -> pd.DataFrame:
        all_payments = []
        end_date = pd.Timestamp("2024-12-31")
        start_date = end_date - pd.DateOffset(months=self.months)

        for _, row in self.borrowers.iterrows():
            monthly_payment = row["requested_loan_amount"] / max(self.months, 1)

            # Payment reliability based on observable credit features (not default label)
            dti = row.get("debt_to_income_ratio", 0.3)
            n_delinq = row.get("number_of_delinquencies", 0)
            util = row.get("credit_utilization_ratio", 0.5)

            # Higher DTI / more delinquencies / higher util -> more likely to pay late
            late_prob = min(0.4, 0.03 + 0.1 * min(dti, 2.0) + 0.05 * min(n_delinq, 5) + 0.05 * min(util, 2.0))

            for month_offset in range(self.months):
                due_date = start_date + pd.DateOffset(months=month_offset + 1)
                amount_due = round(monthly_payment, 2)

                if self.rng.random() < late_prob:
                    pay_fraction = max(0.0, self.rng.uniform(0.5, 1.0))
                    days_late = int(self.rng.exponential(10) + 1)
                else:
                    pay_fraction = min(1.0, self.rng.uniform(0.95, 1.05))
                    days_late = 0 if self.rng.random() > 0.05 else int(self.rng.integers(1, 10))

                amount_paid = round(amount_due * pay_fraction, 2)
                payment_date = due_date + pd.Timedelta(days=days_late)

                if amount_paid == 0:
                    status = "missed"
                elif days_late > 0:
                    status = "late"
                else:
                    status = "on_time"

                all_payments.append({
                    "borrower_id": row["borrower_id"],
                    "payment_date": payment_date,
                    "due_date": due_date,
                    "amount_due": amount_due,
                    "amount_paid": amount_paid,
                    "days_past_due": days_late,
                    "payment_status": status,
                })

        return pd.DataFrame(all_payments)


def generate_full_dataset(settings: DataSettings) -> dict[str, pd.DataFrame]:
    """Generate all three datasets. Returns dict with borrowers, transactions, payments."""
    print("Generating borrower profiles...")
    borrower_gen = BorrowerProfileGenerator(settings)
    borrowers = borrower_gen.generate()
    print(f"  {len(borrowers)} borrowers generated (default rate: {borrowers['is_default'].mean():.3f})")

    print("Generating transaction histories...")
    txn_gen = TransactionGenerator(borrowers, settings)
    transactions = txn_gen.generate()
    print(f"  {len(transactions)} transactions generated")

    print("Generating payment histories...")
    pmt_gen = PaymentHistoryGenerator(borrowers, settings)
    payments = pmt_gen.generate()
    print(f"  {len(payments)} payment records generated")

    return {
        "borrowers": borrowers,
        "transactions": transactions,
        "payments": payments,
    }


def generate_enrichment_for_existing(
    borrowers: pd.DataFrame, settings: DataSettings
) -> dict[str, pd.DataFrame]:
    """Generate only transactions and payments for existing borrower data (e.g., from Kaggle)."""
    print("Generating transaction histories for existing borrowers...")
    txn_gen = TransactionGenerator(borrowers, settings)
    transactions = txn_gen.generate()
    print(f"  {len(transactions)} transactions generated")

    print("Generating payment histories for existing borrowers...")
    pmt_gen = PaymentHistoryGenerator(borrowers, settings)
    payments = pmt_gen.generate()
    print(f"  {len(payments)} payment records generated")

    return {
        "transactions": transactions,
        "payments": payments,
    }
