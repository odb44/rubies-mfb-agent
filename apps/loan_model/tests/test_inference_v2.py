import pytest
from rubies_loan_model.inference_v2 import LoanModelInferenceV2
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


@pytest.fixture
def inference_service() -> LoanModelInferenceV2:
    return LoanModelInferenceV2()


def test_v2_model_loads(inference_service):
    assert inference_service.model_version == "loan-logreg-v2"


def test_selected_threshold_is_loaded_from_manifest(
    inference_service,
):
    assert inference_service.classification_threshold == 0.25


def test_prediction_returns_expected_structure(
    inference_service,
    applicant,
):
    result = inference_service.predict(applicant)

    assert result.model_version == "loan-logreg-v2"
    assert result.predicted_delinquent in {0, 1}

    assert 0 <= result.probability_delinquent <= 1
    assert 0 <= result.probability_not_delinquent <= 1

    assert (result.probability_delinquent + result.probability_not_delinquent) == pytest.approx(1.0)


def test_prediction_uses_manifest_threshold(
    inference_service,
    applicant,
):
    result = inference_service.predict(applicant)

    expected_prediction = int(result.probability_delinquent >= 0.25)

    assert result.predicted_delinquent == expected_prediction


def test_prediction_does_not_make_lending_decision(
    inference_service,
    applicant,
):
    result = inference_service.predict(applicant)

    assert result.lending_decision == "NOT_DETERMINED"

    assert "synthetic" in result.warning.lower()


def test_invalid_model_version_is_rejected():
    with pytest.raises(ValueError, match="Invalid model version"):
        LoanModelInferenceV2(model_version="../loan-logreg-v1")


def test_wrong_applicant_type_is_rejected(
    inference_service,
):
    with pytest.raises(TypeError, match="LoanApplicantInputV2"):
        inference_service.predict({"monthly_income_ngn": 300_000})
