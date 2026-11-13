
"""Request and response schemas for loan eligibility assessments."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoanEligibilityRequest(BaseModel):
    """Customer's requested preliminary eligibility assessment."""

    model_config = ConfigDict(extra="forbid")

    product_code: str = Field(min_length=1, max_length=40)
    requested_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    term_months: int = Field(gt=0, le=120)


class LoanEligibilityResponse(BaseModel):
    """Structured preliminary eligibility assessment."""

    result: Literal[
        "ELIGIBLE_FOR_REVIEW",
        "NOT_ELIGIBLE_UNDER_CURRENT_RULES",
        "INSUFFICIENT_DATA",
        "OUT_OF_SCOPE",
    ]
    product_code: str
    requested_amount: Decimal
    term_months: int
    currency: str
    disposable_income: Decimal | None
    estimated_monthly_principal: Decimal | None
    reason_codes: list[str]
    explanation: str
    policy_document_id: str
    policy_version: str
    ruleset_version: str
    assessed_at: datetime
    correlation_id: str
