import asyncio
from unittest.mock import patch

import pytest
from rubies_agent.tools.loan_tools import assess_loan_delinquency_risk
from rubies_loan_model.schemas_v2 import LoanModelPredictionV2


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def valid_arguments():
    return {
        "employment_type": "SALARIED",
        "monthly_income_ngn": 300_000,
        "monthly_expenses_ngn": 120_000,
        "existing_monthly_debt_ngn": 30_000,
        "requested_amount_ngn": 240_000,
        "term_months": 6,
        "repayment_frequency": "MONTHLY",
        "previous_loan_count": 2,
        "previous_repayment_rate": 0.9,
        "previous_default_count": 0,
    }


class FakeInference:
    def predict(self, applicant):
        return LoanModelPredictionV2(
            model_version="loan-logreg-v2",
            predicted_delinquent=1,
            probability_delinquent=0.65,
            probability_not_delinquent=0.35,
        )


def test_risk_tool_returns_synthetic_prediction(valid_arguments):
    async def scenario():
        with patch(
            "rubies_agent.tools.loan_tools._get_loan_model",
            return_value=FakeInference(),
        ):
            result = await assess_loan_delinquency_risk(**valid_arguments)

        assert result["success"] is True
        assert result["status"] == "SYNTHETIC_RISK_ESTIMATE"
        assert result["model_version"] == "loan-logreg-v2"
        assert result["predicted_delinquent"] == 1
        assert result["risk_assessment"] == ("ELEVATED_MODEL_ESTIMATED_RISK")
        assert result["probability_delinquent_percentage"] == 65.0
        assert result["lending_decision"] == "NOT_DETERMINED"
        assert "synthetic" in result["customer_disclaimer"].lower()

    run(scenario())


def test_risk_tool_does_not_make_lending_decision(valid_arguments):
    async def scenario():
        with patch(
            "rubies_agent.tools.loan_tools._get_loan_model",
            return_value=FakeInference(),
        ):
            result = await assess_loan_delinquency_risk(**valid_arguments)

        assert result["lending_decision"] == "NOT_DETERMINED"

    run(scenario())


def test_risk_tool_rejects_invalid_applicant_input(valid_arguments):
    async def scenario():
        valid_arguments["monthly_income_ngn"] = -100

        result = await assess_loan_delinquency_risk(**valid_arguments)

        assert result["success"] is False
        assert result["status"] == "INVALID_APPLICANT_INPUT"

    run(scenario())


def test_risk_tool_handles_missing_model(valid_arguments):
    async def scenario():
        with patch(
            "rubies_agent.tools.loan_tools._get_loan_model",
            side_effect=FileNotFoundError("Model artifact missing"),
        ):
            result = await assess_loan_delinquency_risk(**valid_arguments)

        assert result["success"] is False
        assert result["status"] == "MODEL_UNAVAILABLE"

    run(scenario())


def test_risk_tool_handles_inference_failure(valid_arguments):
    async def scenario():
        with patch(
            "rubies_agent.tools.loan_tools._get_loan_model",
            side_effect=RuntimeError("Inference failed"),
        ):
            result = await assess_loan_delinquency_risk(**valid_arguments)

        assert result["success"] is False
        assert result["status"] == "MODEL_UNAVAILABLE"

    run(scenario())
