"""Feature definitions with metadata for the credit scoring system."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FeatureGroup(StrEnum):
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


def _fd(name, desc, dtype, group, source, nullable=False):
    return FeatureDefinition(name, desc, dtype, group, source, nullable)


_D = FeatureGroup.DEMOGRAPHIC
_C = FeatureGroup.CREDIT_HISTORY
_V = FeatureGroup.VELOCITY
_A = FeatureGroup.AGGREGATION
_B = FeatureGroup.BEHAVIORAL
_T = FeatureGroup.TIME_SERIES
_R = FeatureGroup.RISK

FEATURE_REGISTRY: list[FeatureDefinition] = [
    # Demographic
    _fd("age", "Borrower age in years", "float64", _D, "borrowers"),
    _fd("log_annual_income", "Log of annual income", "float64", _D, "computed"),
    _fd("employment_length_years", "Years at current employer", "float64", _D, "borrowers"),
    _fd("account_age_months", "Months since account creation", "int64", _D, "borrowers"),
    _fd("profile_completeness_score", "Fraction of profile fields filled", "float64", _D, "borrowers"),
    # Credit history
    _fd("credit_utilization_ratio", "Current balance / credit limit", "float64", _C, "borrowers"),
    _fd("existing_credit_lines", "Number of open credit lines", "int64", _C, "borrowers"),
    _fd(
        "months_since_last_delinquency",
        "Months since last late payment",
        "float64",
        _C,
        "borrowers",
        nullable=True,
    ),
    _fd("number_of_delinquencies", "Total delinquencies on record", "int64", _C, "borrowers"),
    _fd("debt_to_income_ratio", "Total debt / annual income", "float64", _C, "borrowers"),
    # Velocity
    _fd("txn_count_7d", "Transaction count in last 7 days", "int64", _V, "computed"),
    _fd("txn_count_30d", "Transaction count in last 30 days", "int64", _V, "computed"),
    _fd("txn_count_90d", "Transaction count in last 90 days", "int64", _V, "computed"),
    _fd("txn_amount_sum_7d", "Total spend in last 7 days", "float64", _V, "computed"),
    _fd("txn_amount_sum_30d", "Total spend in last 30 days", "float64", _V, "computed"),
    _fd("txn_amount_mean_30d", "Avg transaction in last 30 days", "float64", _V, "computed"),
    _fd("txn_amount_std_30d", "Std dev of transactions in 30 days", "float64", _V, "computed"),
    _fd("txn_amount_max_30d", "Max single transaction in 30 days", "float64", _V, "computed"),
    _fd("decline_rate_30d", "Fraction of declined txns in 30 days", "float64", _V, "computed"),
    _fd("international_txn_rate_30d", "Fraction of international txns", "float64", _V, "computed"),
    # Aggregation
    _fd("avg_spend_grocery", "Average monthly grocery spend", "float64", _A, "computed"),
    _fd("avg_spend_restaurant", "Average monthly restaurant spend", "float64", _A, "computed"),
    _fd("avg_spend_online", "Average monthly online spend", "float64", _A, "computed"),
    _fd("avg_spend_travel", "Average monthly travel spend", "float64", _A, "computed"),
    _fd("merchant_diversity_30d", "Unique merchant categories in 30d", "int64", _A, "computed"),
    _fd("channel_diversity", "Unique channels used", "int64", _A, "computed"),
    _fd("spend_category_entropy", "Shannon entropy of spend categories", "float64", _A, "computed"),
    # Behavioral
    _fd("mobile_txn_fraction", "Fraction of mobile transactions", "float64", _B, "computed"),
    _fd("weekend_txn_fraction", "Fraction of weekend transactions", "float64", _B, "computed"),
    _fd("nighttime_txn_fraction", "Fraction of transactions 10pm-6am", "float64", _B, "computed"),
    # Time series
    _fd("spend_trend_3m", "Linear trend of monthly spend (3m)", "float64", _T, "computed"),
    _fd("spend_trend_6m", "Linear trend of monthly spend (6m)", "float64", _T, "computed"),
    _fd("spend_volatility_6m", "CV of monthly spend", "float64", _T, "computed"),
    _fd("txn_frequency_trend", "Trend in monthly transaction count", "float64", _T, "computed"),
    # Payment risk
    _fd("on_time_payment_rate", "Fraction of on-time payments", "float64", _R, "computed"),
    _fd("avg_days_past_due", "Average days past due", "float64", _R, "computed"),
    _fd("max_days_past_due", "Maximum days past due ever", "int64", _R, "computed"),
    _fd("missed_payment_count", "Total missed payments", "int64", _R, "computed"),
    _fd("payment_amount_ratio", "Average (paid / due)", "float64", _R, "computed"),
    _fd("consecutive_on_time", "Current on-time payment streak", "int64", _R, "computed"),
    _fd("payment_trend_3m", "Trend in payment timeliness (3m)", "float64", _R, "computed"),
    # Risk ratios
    _fd("loan_to_income_ratio", "Requested loan / annual income", "float64", _R, "computed"),
    _fd("balance_to_income_ratio", "Credit balance / annual income", "float64", _R, "computed"),
    _fd("utilization_x_dti", "Interaction: utilization * DTI", "float64", _R, "computed"),
    _fd("income_stability_proxy", "employment_length / age", "float64", _R, "computed"),
]


def get_feature_names(group: FeatureGroup | None = None) -> list[str]:
    if group is None:
        return [f.name for f in FEATURE_REGISTRY]
    return [f.name for f in FEATURE_REGISTRY if f.group == group]


def get_feature_definitions() -> list[FeatureDefinition]:
    return FEATURE_REGISTRY
