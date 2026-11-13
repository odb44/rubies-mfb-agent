"""Input and output schemas for the loan-model inference service."""

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class LoanApplicantInput:
    """Applicant features expected by the historical Kaggle model."""

    Gender: str
    Married: str
    Dependents: str
    Education: str
    Self_Employed: str
    ApplicantIncome: float
    CoapplicantIncome: float
    LoanAmount: float
    Loan_Amount_Term: float
    Credit_History: str
    Property_Area: str

    def validate(self) -> None:
        """Reject missing, invalid, or unsupported input values."""

        categorical_options = {
            "Gender": {"Male", "Female"},
            "Married": {"Yes", "No"},
            "Dependents": {"0", "1", "2", "3+"},
            "Education": {"Graduate", "Not Graduate"},
            "Self_Employed": {"Yes", "No"},
            "Credit_History": {"0", "1"},
            "Property_Area": {"Urban", "Semiurban", "Rural"},
        }

        for field_name, allowed_values in categorical_options.items():
            value = getattr(self, field_name)
            if not isinstance(value, str) or value not in allowed_values:
                raise ValueError(f"{field_name} must be one of {sorted(allowed_values)}.")

        numeric_fields = (
            "ApplicantIncome",
            "CoapplicantIncome",
            "LoanAmount",
            "Loan_Amount_Term",
        )

        for field_name in numeric_fields:
            value = getattr(self, field_name)

            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{field_name} must be numeric.")

            if not isfinite(value):
                raise ValueError(f"{field_name} must be finite.")

            if value < 0:
                raise ValueError(f"{field_name} cannot be negative.")

        if self.LoanAmount <= 0:
            raise ValueError("LoanAmount must be greater than zero.")

        if self.Loan_Amount_Term <= 0:
            raise ValueError("Loan_Amount_Term must be greater than zero.")

    def to_model_features(self) -> dict[str, Any]:
        """Validate input and derive the engineered training features."""

        self.validate()

        total_income = self.ApplicantIncome + self.CoapplicantIncome

        features = asdict(self)
        features["TotalIncome"] = total_income
        features["IncomeToLoanAmountRatio"] = total_income / self.LoanAmount

        return features


@dataclass(frozen=True)
class LoanModelPrediction:
    """Prediction from the historical loan model, not a lending decision."""

    model_version: str
    predicted_historical_status: str
    probability_historical_no: float
    probability_historical_yes: float
    intended_use: str = "Capstone demonstration only"
    lending_decision: str = "NOT_DETERMINED"
    warning: str = (
        "This model predicts historical Kaggle Loan_Status labels. "
        "It is not validated for Rubies MFB eligibility or lending decisions."
    )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return asdict(self)
