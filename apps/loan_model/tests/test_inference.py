import pytest
from rubies_loan_model.inference import LoanModelInference
from rubies_loan_model.schemas import LoanApplicantInput


@pytest.fixture
def applicant() -> LoanApplicantInput:
    return LoanApplicantInput(
        Gender="Male",
        Married="Yes",
        Dependents="0",
        Education="Graduate",
        Self_Employed="No",
        ApplicantIncome=5000,
        CoapplicantIncome=1000,
        LoanAmount=120,
        Loan_Amount_Term=360,
        Credit_History="1",
        Property_Area="Urban",
    )


def test_engineered_features_are_calculated(applicant: LoanApplicantInput) -> None:
    features = applicant.to_model_features()

    assert features["TotalIncome"] == 6000
    assert features["IncomeToLoanAmountRatio"] == 50


def test_invalid_loan_amount_is_rejected(applicant: LoanApplicantInput) -> None:
    invalid_applicant = LoanApplicantInput(**{**applicant.__dict__, "LoanAmount": 0})

    with pytest.raises(ValueError, match="LoanAmount"):
        invalid_applicant.to_model_features()


def test_model_loads_and_returns_prediction(
    applicant: LoanApplicantInput,
) -> None:
    service = LoanModelInference()

    result = service.predict(applicant)

    assert result.model_version == "loan-logreg-v1"
    assert result.predicted_historical_status in {"Y", "N"}
    assert 0 <= result.probability_historical_yes <= 1
    assert 0 <= result.probability_historical_no <= 1
    assert (result.probability_historical_yes + result.probability_historical_no) == pytest.approx(
        1.0
    )
    assert result.lending_decision == "NOT_DETERMINED"
