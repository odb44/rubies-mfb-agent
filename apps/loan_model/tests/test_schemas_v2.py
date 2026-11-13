import pytest
from rubies_loan_model.schemas_v2 import LoanApplicantInputV2


@pytest.fixture
def applicant() -> LoanApplicantInputV2:
    return LoanApplicantInputV2(
        employment_type="SALARIED",
        monthly_income_ngn=300_000,
        monthly_expenses_ngn=120_000,
        existing_monthly_debt_ngn=30_000,
        requested_amount_ngn=240_000,
        term_months=6,
        repayment_frequency="MONTHLY",
        previous_loan_count=2,
        previous_repayment_rate=0.9,
        previous_default_count=0,
    )


def test_valid_applicant_features_are_engineered(applicant):
    features = applicant.to_model_features()

    assert features["disposable_income_ngn"] == 150_000
    assert features["estimated_monthly_repayment_ngn"] == 40_000
    assert features["repayment_to_income_ratio"] == pytest.approx(40_000 / 300_000)


def test_negative_income_is_rejected(applicant):
    invalid = LoanApplicantInputV2(**{**applicant.__dict__, "monthly_income_ngn": -1})

    with pytest.raises(ValueError, match="monthly_income_ngn"):
        invalid.to_model_features()


def test_invalid_employment_type_is_rejected(applicant):
    invalid = LoanApplicantInputV2(**{**applicant.__dict__, "employment_type": "CONTRACTOR"})

    with pytest.raises(ValueError, match="employment_type"):
        invalid.to_model_features()


def test_previous_defaults_cannot_exceed_previous_loans(applicant):
    invalid = LoanApplicantInputV2(**{**applicant.__dict__, "previous_default_count": 3})

    with pytest.raises(ValueError, match="previous_default_count"):
        invalid.to_model_features()


def test_negative_disposable_income_is_allowed(applicant):
    invalid = LoanApplicantInputV2(
        **{
            **applicant.__dict__,
            "monthly_expenses_ngn": 250_000,
            "existing_monthly_debt_ngn": 100_000,
        }
    )

    features = invalid.to_model_features()

    assert features["disposable_income_ngn"] == -50_000


def test_invalid_repayment_rate_is_rejected(applicant):
    invalid = LoanApplicantInputV2(**{**applicant.__dict__, "previous_repayment_rate": 1.5})

    with pytest.raises(ValueError, match="previous_repayment_rate"):
        invalid.to_model_features()
