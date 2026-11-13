"""Input and output schemas for the synthetic loan delinquency model V2."""

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any

EMPLOYMENT_TYPES = {
    "SALARIED",
    "SELF_EMPLOYED",
    "BUSINESS_OWNER",
    "UNEMPLOYED",
}

REPAYMENT_FREQUENCIES = {
    "WEEKLY",
    "BIWEEKLY",
    "MONTHLY",
}

FEATURE_SCHEMA_VERSION = "loan-applicant-features-v2"


@dataclass(frozen=True)
class LoanApplicantInputV2:
    """Applicant and loan features for predicting 90-day delinquency."""

    employment_type: str
    monthly_income_ngn: float
    monthly_expenses_ngn: float
    existing_monthly_debt_ngn: float
    requested_amount_ngn: float
    term_months: int
    repayment_frequency: str
    previous_loan_count: int
    previous_repayment_rate: float
    previous_default_count: int

    def validate(self) -> None:
        """Validate applicant features before model inference."""

        if self.employment_type not in EMPLOYMENT_TYPES:
            raise ValueError(f"employment_type must be one of {sorted(EMPLOYMENT_TYPES)}.")

        if self.repayment_frequency not in REPAYMENT_FREQUENCIES:
            raise ValueError(f"repayment_frequency must be one of {sorted(REPAYMENT_FREQUENCIES)}.")

        numeric_fields = (
            "monthly_income_ngn",
            "monthly_expenses_ngn",
            "existing_monthly_debt_ngn",
            "requested_amount_ngn",
            "previous_repayment_rate",
        )

        for field_name in numeric_fields:
            value = getattr(self, field_name)

            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{field_name} must be numeric.")

            if not isfinite(value):
                raise ValueError(f"{field_name} must be finite.")

            if value < 0:
                raise ValueError(f"{field_name} cannot be negative.")

        if self.monthly_income_ngn <= 0:
            raise ValueError("monthly_income_ngn must be greater than zero.")

        if self.requested_amount_ngn <= 0:
            raise ValueError("requested_amount_ngn must be greater than zero.")

        if isinstance(self.term_months, bool) or not isinstance(self.term_months, int):
            raise ValueError("term_months must be an integer.")

        if not 1 <= self.term_months <= 12:
            raise ValueError("term_months must be between 1 and 12.")

        integer_fields = (
            "previous_loan_count",
            "previous_default_count",
        )

        for field_name in integer_fields:
            value = getattr(self, field_name)

            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{field_name} must be an integer.")

            if value < 0:
                raise ValueError(f"{field_name} cannot be negative.")

        if self.previous_loan_count > 8:
            raise ValueError("previous_loan_count cannot exceed 8.")

        if self.previous_default_count > 3:
            raise ValueError("previous_default_count cannot exceed 3.")

        if self.previous_default_count > self.previous_loan_count:
            raise ValueError("previous_default_count cannot exceed previous_loan_count.")

        if not 0 <= self.previous_repayment_rate <= 1:
            raise ValueError("previous_repayment_rate must be between 0 and 1.")

    def to_model_features(self) -> dict[str, Any]:
        """Validate input and derive the V2 model features."""

        self.validate()

        features = asdict(self)

        disposable_income = (
            self.monthly_income_ngn - self.monthly_expenses_ngn - self.existing_monthly_debt_ngn
        )

        # Initial estimate uses principal only.
        # Interest, fees and repayment-frequency adjustments are excluded.
        estimated_monthly_repayment = self.requested_amount_ngn / self.term_months

        repayment_to_income_ratio = estimated_monthly_repayment / self.monthly_income_ngn

        features["disposable_income_ngn"] = disposable_income
        features["estimated_monthly_repayment_ngn"] = estimated_monthly_repayment
        features["repayment_to_income_ratio"] = repayment_to_income_ratio

        return features


@dataclass(frozen=True)
class LoanModelPredictionV2:
    """Delinquency prediction, not a lending approval or rejection."""

    model_version: str
    predicted_delinquent: int
    probability_delinquent: float
    probability_not_delinquent: float
    target: str = "DELINQUENT_WITHIN_90_DAYS"
    intended_use: str = "Synthetic capstone demonstration only"
    lending_decision: str = "NOT_DETERMINED"
    warning: str = (
        "This model was trained on synthetic data. "
        "It is not validated for real Rubies MFB lending decisions."
    )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return asdict(self)
