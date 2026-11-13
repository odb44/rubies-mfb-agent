"""Loan tools for the Rubies MFB support agent."""

from functools import lru_cache
from typing import Any

from rubies_loan_model.inference_v2 import LoanModelInferenceV2
from rubies_loan_model.schemas_v2 import LoanApplicantInputV2
from strands import ToolContext, tool

from rubies_agent.services.banking_tool_executor import call_banking_tool


@lru_cache(maxsize=1)
def _get_loan_model() -> LoanModelInferenceV2:
    """Load the V2 model once and reuse it across tool calls."""

    return LoanModelInferenceV2()


@tool(context=True)
async def check_loan_eligibility(
    product_code: str,
    requested_amount: str,
    term_months: int,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """
    Check preliminary loan eligibility using the authenticated
    customer's existing banking data.

    Supported products:
    - SALARY_ADVANCE: ₦20,000–₦200,000, 1–3 months.
    - MICRO_BUSINESS: ₦50,000–₦500,000, 3–6 months.

    This is a preliminary assessment, not a loan approval.
    """

    try:
        access_token = tool_context.invocation_state.get("access_token")

        if not isinstance(access_token, str) or not access_token.strip():
            raise RuntimeError(
                "Authenticated customer access token is unavailable."
            )

        return await call_banking_tool(
            "check_loan_eligibility",
            {
                "product_code": product_code,
                "requested_amount": requested_amount,
                "term_months": term_months,
            },
            access_token=access_token,
        )

    except RuntimeError as exc:
        return {
            "success": False,
            "status": "SERVICE_ERROR",
            "error": str(exc),
        }


@tool
async def get_loan_status() -> dict[str, Any]:
    """Retrieve all loan accounts and applications belonging
    to the authenticated customer.
    """
    try:
        return await call_banking_tool("get_loan_status", {})
    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
        }


@tool
async def assess_loan_delinquency_risk(
    employment_type: str,
    monthly_income_ngn: float,
    monthly_expenses_ngn: float,
    existing_monthly_debt_ngn: float,
    requested_amount_ngn: float,
    term_months: int,
    repayment_frequency: str,
    previous_loan_count: int,
    previous_repayment_rate: float,
    previous_default_count: int,
) -> dict[str, Any]:
    """Estimate synthetic 90-day loan delinquency risk.

    Requires applicant and requested-loan information.

    This is an experimental demonstration using synthetic training data.
    It is NOT a loan eligibility assessment, approval, rejection,
    credit bureau check, or lending decision.

    Never present this prediction as an authoritative assessment
    of a customer's actual repayment behaviour.
    """

    try:
        applicant = LoanApplicantInputV2(
            employment_type=employment_type,
            monthly_income_ngn=monthly_income_ngn,
            monthly_expenses_ngn=monthly_expenses_ngn,
            existing_monthly_debt_ngn=existing_monthly_debt_ngn,
            requested_amount_ngn=requested_amount_ngn,
            term_months=term_months,
            repayment_frequency=repayment_frequency,
            previous_loan_count=previous_loan_count,
            previous_repayment_rate=previous_repayment_rate,
            previous_default_count=previous_default_count,
        )

        prediction = _get_loan_model().predict(applicant)

        result = prediction.to_dict()

        result.update(
            {
                "success": True,
                "status": "SYNTHETIC_RISK_ESTIMATE",
                "risk_assessment": (
                    "ELEVATED_MODEL_ESTIMATED_RISK"
                    if prediction.predicted_delinquent == 1
                    else "LOWER_MODEL_ESTIMATED_RISK"
                ),
                "probability_delinquent_percentage": round(
                    prediction.probability_delinquent * 100,
                    2,
                ),
                "probability_not_delinquent_percentage": round(
                    prediction.probability_not_delinquent * 100,
                    2,
                ),
                "lending_decision": "NOT_DETERMINED",
                "customer_disclaimer": (
                    "This is an experimental prediction from synthetic data. "
                    "It is not validated against actual Rubies MFB loan "
                    "performance and must not be used to approve or reject "
                    "a loan."
                ),
            }
        )

        return result

    except ValueError as exc:
        return {
            "success": False,
            "status": "INVALID_APPLICANT_INPUT",
            "message": str(exc),
        }

    except (FileNotFoundError, RuntimeError, OSError):
        return {
            "success": False,
            "status": "MODEL_UNAVAILABLE",
            "message": ("The experimental loan-risk assessment is currently unavailable."),
        }

    except Exception:
        return {
            "success": False,
            "status": "MODEL_INFERENCE_FAILED",
            "message": ("The experimental loan-risk assessment could not be completed."),
        }
