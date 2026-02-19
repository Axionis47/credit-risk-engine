"""Feature definitions with metadata for the credit scoring system."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FeatureGroup(str, Enum):
    DEMOGRAPHIC = "demographic"
    CREDIT_HISTORY = "credit_history"
    VELOCITY = "velocity"
    AGGREGATION = "aggregation"
    BEHAVIORAL = "behavioral"
    TIME_SERIES = "time_series"
    RISK = "risk"


@dataclass
class FeatureDefinition:
    name: str
    description: str
    dtype: str
    group: FeatureGroup
    source: str  # "borrowers", "transactions", "payments", "computed"
    nullable: bool = False


FEATURE_REGISTRY: list[FeatureDefinition] = [
    # Demographic
    FeatureDefinition("age", "Borrower age in years", "float64", FeatureGroup.DEMOGRAPHIC, "borrowers"),
    FeatureDefinition("log_annual_income", "Log of annual income", "float64", FeatureGroup.DEMOGRAPHIC, "computed"),
    FeatureDefinition("employment_length_years", "Years at current employer", "float64", FeatureGroup.DEMOGRAPHIC, "borrowers"),
    FeatureDefinition("account_age_months", "Months since account creation", "int64", FeatureGroup.DEMOGRAPHIC, "borrowers"),
    FeatureDefinition("profile_completeness_score", "Fraction of profile fields filled", "float64", FeatureGroup.DEMOGRAPHIC, "borrowers"),
    # Credit history
    FeatureDefinition("credit_utilization_ratio", "Current balance / credit limit", "float64", FeatureGroup.CREDIT_HISTORY, "borrowers"),
    FeatureDefinition("existing_credit_lines", "Number of open credit lines", "int64", FeatureGroup.CREDIT_HISTORY, "borrowers"),
    FeatureDefinition("months_since_last_delinquency", "Months since last late payment", "float64", FeatureGroup.CREDIT_HISTORY, "borrowers", nullable=True),
    FeatureDefinition("number_of_delinquencies", "Total delinquencies on record", "int64", FeatureGroup.CREDIT_HISTORY, "borrowers"),
    FeatureDefinition("debt_to_income_ratio", "Total debt / annual income", "float64", FeatureGroup.CREDIT_HISTORY, "borrowers"),
    # Velocity
    FeatureDefinition("txn_count_7d", "Transaction count in last 7 days", "int64", FeatureGroup.VELOCITY, "computed"),
    FeatureDefinition("txn_count_30d", "Transaction count in last 30 days", "int64", FeatureGroup.VELOCITY, "computed"),
    FeatureDefinition("txn_count_90d", "Transaction count in last 90 days", "int64", FeatureGroup.VELOCITY, "computed"),
    FeatureDefinition("txn_amount_sum_7d", "Total spend in last 7 days", "float64", FeatureGroup.VELOCITY, "computed"),
    FeatureDefinition("txn_amount_sum_30d", "Total spend in last 30 days", "float64", FeatureGroup.VELOCITY, "computed"),
    FeatureDefinition("txn_amount_mean_30d", "Average transaction in last 30 days", "float64", FeatureGroup.VELOCITY, "computed"),
    FeatureDefinition("txn_amount_std_30d", "Std dev of transactions in last 30 days", "float64", FeatureGroup.VELOCITY, "computed"),
    FeatureDefinition("txn_amount_max_30d", "Max single transaction in last 30 days", "float64", FeatureGroup.VELOCITY, "computed"),
    FeatureDefinition("decline_rate_30d", "Fraction of declined transactions in 30 days", "float64", FeatureGroup.VELOCITY, "computed"),
    FeatureDefinition("international_txn_rate_30d", "Fraction of international transactions", "float64", FeatureGroup.VELOCITY, "computed"),
    # Aggregation
    FeatureDefinition("avg_spend_grocery", "Average monthly grocery spend", "float64", FeatureGroup.AGGREGATION, "computed"),
    FeatureDefinition("avg_spend_restaurant", "Average monthly restaurant spend", "float64", FeatureGroup.AGGREGATION, "computed"),
    FeatureDefinition("avg_spend_online", "Average monthly online spend", "float64", FeatureGroup.AGGREGATION, "computed"),
    FeatureDefinition("avg_spend_travel", "Average monthly travel spend", "float64", FeatureGroup.AGGREGATION, "computed"),
    FeatureDefinition("merchant_diversity_30d", "Unique merchant categories in 30 days", "int64", FeatureGroup.AGGREGATION, "computed"),
    FeatureDefinition("channel_diversity", "Unique channels used", "int64", FeatureGroup.AGGREGATION, "computed"),
    FeatureDefinition("spend_category_entropy", "Shannon entropy of spending categories", "float64", FeatureGroup.AGGREGATION, "computed"),
    # Behavioral
    FeatureDefinition("mobile_txn_fraction", "Fraction of mobile transactions", "float64", FeatureGroup.BEHAVIORAL, "computed"),
    FeatureDefinition("weekend_txn_fraction", "Fraction of weekend transactions", "float64", FeatureGroup.BEHAVIORAL, "computed"),
    FeatureDefinition("nighttime_txn_fraction", "Fraction of transactions 10pm-6am", "float64", FeatureGroup.BEHAVIORAL, "computed"),
    # Time series
    FeatureDefinition("spend_trend_3m", "Linear trend of monthly spend over 3 months", "float64", FeatureGroup.TIME_SERIES, "computed"),
    FeatureDefinition("spend_trend_6m", "Linear trend of monthly spend over 6 months", "float64", FeatureGroup.TIME_SERIES, "computed"),
    FeatureDefinition("spend_volatility_6m", "Coefficient of variation of monthly spend", "float64", FeatureGroup.TIME_SERIES, "computed"),
    FeatureDefinition("txn_frequency_trend", "Trend in monthly transaction count", "float64", FeatureGroup.TIME_SERIES, "computed"),
    # Payment risk
    FeatureDefinition("on_time_payment_rate", "Fraction of on-time payments", "float64", FeatureGroup.RISK, "computed"),
    FeatureDefinition("avg_days_past_due", "Average days past due across payments", "float64", FeatureGroup.RISK, "computed"),
    FeatureDefinition("max_days_past_due", "Maximum days past due ever", "int64", FeatureGroup.RISK, "computed"),
    FeatureDefinition("missed_payment_count", "Total missed payments", "int64", FeatureGroup.RISK, "computed"),
    FeatureDefinition("payment_amount_ratio", "Average (amount_paid / amount_due)", "float64", FeatureGroup.RISK, "computed"),
    FeatureDefinition("consecutive_on_time", "Current streak of on-time payments", "int64", FeatureGroup.RISK, "computed"),
    FeatureDefinition("payment_trend_3m", "Trend in payment timeliness over 3 months", "float64", FeatureGroup.RISK, "computed"),
    # Risk ratios
    FeatureDefinition("loan_to_income_ratio", "Requested loan / annual income", "float64", FeatureGroup.RISK, "computed"),
    FeatureDefinition("balance_to_income_ratio", "Credit balance / annual income", "float64", FeatureGroup.RISK, "computed"),
    FeatureDefinition("utilization_x_dti", "Interaction: utilization * DTI", "float64", FeatureGroup.RISK, "computed"),
    FeatureDefinition("income_stability_proxy", "employment_length / age", "float64", FeatureGroup.RISK, "computed"),
]


def get_feature_names(group: FeatureGroup | None = None) -> list[str]:
    if group is None:
        return [f.name for f in FEATURE_REGISTRY]
    return [f.name for f in FEATURE_REGISTRY if f.group == group]


def get_feature_definitions() -> list[FeatureDefinition]:
    return FEATURE_REGISTRY
