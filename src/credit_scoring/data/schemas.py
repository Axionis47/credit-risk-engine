"""Pydantic schemas for credit scoring data records."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EmploymentType(str, Enum):
    EMPLOYED = "employed"
    SELF_EMPLOYED = "self_employed"
    UNEMPLOYED = "unemployed"
    RETIRED = "retired"


class HomeOwnership(str, Enum):
    OWN = "own"
    MORTGAGE = "mortgage"
    RENT = "rent"


class LoanPurpose(str, Enum):
    DEBT_CONSOLIDATION = "debt_consolidation"
    HOME_IMPROVEMENT = "home_improvement"
    BUSINESS = "business"
    EDUCATION = "education"
    PERSONAL = "personal"


class BorrowerProfile(BaseModel):
    borrower_id: str
    age: int = Field(ge=18, le=100)
    annual_income: float = Field(gt=0)
    employment_length_years: float = Field(ge=0)
    employment_type: EmploymentType
    home_ownership: HomeOwnership
    existing_credit_lines: int = Field(ge=0)
    total_credit_limit: float = Field(ge=0)
    current_credit_balance: float = Field(ge=0)
    credit_utilization_ratio: float = Field(ge=0.0, le=2.0)
    months_since_last_delinquency: Optional[int] = None
    number_of_delinquencies: int = Field(ge=0)
    debt_to_income_ratio: float = Field(ge=0)
    requested_loan_amount: float = Field(gt=0)
    loan_purpose: LoanPurpose
    state: str = Field(min_length=2, max_length=2)
    account_age_months: int = Field(ge=0)
    profile_completeness_score: float = Field(ge=0.0, le=1.0)
    device_type: str


class Transaction(BaseModel):
    transaction_id: str
    borrower_id: str
    timestamp: datetime
    amount: float = Field(gt=0)
    merchant_category: str
    is_international: bool
    channel: str
    is_declined: bool


class PaymentRecord(BaseModel):
    borrower_id: str
    payment_date: datetime
    due_date: datetime
    amount_due: float = Field(ge=0)
    amount_paid: float = Field(ge=0)
    days_past_due: int = Field(ge=0)
    payment_status: str
