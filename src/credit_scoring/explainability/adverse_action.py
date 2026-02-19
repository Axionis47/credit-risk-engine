"""ECOA-compliant adverse action reason codes."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from credit_scoring.explainability.shap_explainer import SHAPExplainer


@dataclass
class AdverseActionReason:
    code: str
    description: str
    feature: str
    impact_score: float


# Feature to adverse action code mapping
# Age is intentionally excluded (protected class under ECOA)
ADVERSE_ACTION_CODE_MAP = {
    "credit_utilization_ratio": ("AA001", "High credit utilization ratio"),
    "debt_to_income_ratio": ("AA002", "High debt-to-income ratio"),
    "number_of_delinquencies": ("AA003", "Number of delinquent accounts"),
    "months_since_last_delinquency": ("AA004", "Recent delinquency on record"),
    "on_time_payment_rate": ("AA005", "Insufficient payment history"),
    "missed_payment_count": ("AA006", "Number of missed payments"),
    "existing_credit_lines": ("AA007", "Limited number of credit accounts"),
    "account_age_months": ("AA008", "Insufficient account history"),
    "employment_length_years": ("AA009", "Length of employment"),
    "loan_to_income_ratio": ("AA010", "Requested amount relative to income"),
    "avg_days_past_due": ("AA011", "Average days past due on accounts"),
    "max_days_past_due": ("AA012", "Severe delinquency on record"),
    "spend_trend_6m": ("AA013", "Increasing spending trend"),
    "txn_amount_max_30d": ("AA014", "Unusually large recent transactions"),
    "decline_rate_30d": ("AA015", "High rate of declined transactions"),
    "international_txn_rate_30d": ("AA016", "High rate of international transactions"),
    "balance_to_income_ratio": ("AA017", "High balance relative to income"),
    "profile_completeness_score": ("AA018", "Incomplete application profile"),
    "payment_amount_ratio": ("AA019", "Insufficient payment amounts"),
    "consecutive_on_time": ("AA020", "Short streak of on-time payments"),
}

# Protected features that must never appear in adverse action reasons
PROTECTED_FEATURES = {"age", "state_encoded"}


class AdverseActionGenerator:
    """Generate adverse action reasons from SHAP explanations."""

    def __init__(self, shap_explainer: SHAPExplainer):
        self.explainer = shap_explainer

    def generate_reasons(
        self, X_single: pd.DataFrame, max_reasons: int = 4
    ) -> list[AdverseActionReason]:
        """Generate up to max_reasons adverse action codes for a declined application."""
        explanation = self.explainer.explain_local(X_single)

        reasons = []
        for contrib in explanation["feature_contributions"]:
            if contrib["direction"] != "increases_risk":
                continue

            feature = contrib["feature"]
            if feature in PROTECTED_FEATURES:
                continue

            # Try exact match
            if feature in ADVERSE_ACTION_CODE_MAP:
                code, desc = ADVERSE_ACTION_CODE_MAP[feature]
                reasons.append(AdverseActionReason(
                    code=code,
                    description=desc,
                    feature=feature,
                    impact_score=abs(contrib["shap_value"]),
                ))

            if len(reasons) >= max_reasons:
                break

        return reasons

    def format_for_notice(self, reasons: list[AdverseActionReason]) -> list[dict]:
        """Format reasons for regulatory adverse action notice."""
        return [
            {"code": r.code, "reason": r.description}
            for r in reasons
        ]
