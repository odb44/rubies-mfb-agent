
"""Tests for deterministic loan eligibility assessments."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rubies_banking_api.services.loan_eligibility_service import (
    ELIGIBLE_FOR_REVIEW,
    INSUFFICIENT_DATA,
    NOT_ELIGIBLE_UNDER_CURRENT_RULES,
    OUT_OF_SCOPE,
    LoanEligibilityService,
)
from rubies_security.identity import (
    CustomerMismatchError,
    IdentityVerificationError,
)
from rubies_shared.identity import CustomerIdentity


@pytest.fixture
def identity() -> CustomerIdentity:
    return CustomerIdentity(
        customer_id="CUS-0007",
        session_id="session-001",
        verified=True,
    )


@pytest.fixture
def customer() -> Mock:
    profile = SimpleNamespace(
        employment_type="SALARIED",
        monthly_income=Decimal("150000.00"),
        monthly_expenses=Decimal("50000.00"),
        existing_monthly_debt=Decimal("10000.00"),
        verification_status="VERIFIED",
        verified_at=datetime(2026, 10, 1, 10, 0, tzinfo=UTC),
    )

    customer = Mock()
    customer.id = 7
    customer.customer_reference = "CUS-0007"
    customer.is_active = True
    customer.accounts = [SimpleNamespace(status="ACTIVE")]
    customer.loan_eligibility_profile = profile

    return customer


@pytest.fixture
def repositories() -> tuple[Mock, Mock]:
    customer_repository = Mock()
    audit_repository = Mock()

    return customer_repository, audit_repository


@pytest.fixture
def service(repositories: tuple[Mock, Mock]) -> LoanEligibilityService:
    customer_repository, audit_repository = repositories

    return LoanEligibilityService(
        customer_repository=customer_repository,
        audit_repository=audit_repository,
    )


@pytest.fixture
def assessment_arguments() -> dict:
    return {
        "product_code": "SALARY_ADVANCE",
        "requested_amount": Decimal("120000.00"),
        "term_months": 3,
        "correlation_id": "corr-test-001",
        "now": datetime(2026, 11, 1, 10, 0, tzinfo=UTC),
    }


def test_returns_eligible_for_review_when_policy_rules_are_met(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, audit_repository = repositories
    customer_repository.get_by_reference.return_value = customer

    result = service.assess_eligibility(
        identity,
        **assessment_arguments,
    )

    assert result.result == ELIGIBLE_FOR_REVIEW
    assert result.disposable_income == Decimal("90000.00")
    assert result.estimated_monthly_principal == Decimal("40000.00")
    assert result.currency == "NGN"
    assert result.policy_version == "0.3"
    assert result.correlation_id == "corr-test-001"

    customer_repository.get_by_reference.assert_called_once_with("CUS-0007")
    audit_repository.record.assert_called_once()

    event = audit_repository.record.call_args.args[0]
    assert event.action == "CHECK_LOAN_ELIGIBILITY"
    assert event.outcome == "COMPLETED"
    assert event.details["result"] == ELIGIBLE_FOR_REVIEW
    assert event.details["policy_version"] == "0.3"


def test_returns_not_eligible_when_affordability_threshold_is_not_met(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, _ = repositories
    customer_repository.get_by_reference.return_value = customer

    customer.loan_eligibility_profile.monthly_income = Decimal("70000.00")

    result = service.assess_eligibility(
        identity,
        **assessment_arguments,
    )

    assert result.result == NOT_ELIGIBLE_UNDER_CURRENT_RULES
    assert "AFFORDABILITY_THRESHOLD_NOT_MET" in result.reason_codes
    assert result.disposable_income == Decimal("10000.00")


def test_returns_insufficient_data_for_unverified_profile(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, _ = repositories
    customer_repository.get_by_reference.return_value = customer

    customer.loan_eligibility_profile.verification_status = "UNVERIFIED"

    result = service.assess_eligibility(
        identity,
        **assessment_arguments,
    )

    assert result.result == INSUFFICIENT_DATA
    assert result.reason_codes == ("FINANCIAL_PROFILE_NOT_VERIFIED",)


def test_returns_insufficient_data_when_profile_is_missing(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, _ = repositories
    customer_repository.get_by_reference.return_value = customer

    customer.loan_eligibility_profile = None

    result = service.assess_eligibility(
        identity,
        **assessment_arguments,
    )

    assert result.result == INSUFFICIENT_DATA
    assert result.reason_codes == ("ELIGIBILITY_PROFILE_MISSING",)


def test_returns_insufficient_data_when_financial_field_is_missing(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, _ = repositories
    customer_repository.get_by_reference.return_value = customer

    customer.loan_eligibility_profile.monthly_expenses = None

    result = service.assess_eligibility(
        identity,
        **assessment_arguments,
    )

    assert result.result == INSUFFICIENT_DATA
    assert result.reason_codes == ("REQUIRED_FINANCIAL_DATA_MISSING",)


def test_returns_out_of_scope_for_unsupported_product(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, _ = repositories
    customer_repository.get_by_reference.return_value = customer

    assessment_arguments["product_code"] = "PERSONAL_LOAN"

    result = service.assess_eligibility(
        identity,
        **assessment_arguments,
    )

    assert result.result == OUT_OF_SCOPE
    assert result.reason_codes == ("UNSUPPORTED_LOAN_PRODUCT",)


def test_rejects_unverified_customer_identity(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    assessment_arguments: dict,
) -> None:
    customer_repository, audit_repository = repositories

    unverified_identity = CustomerIdentity(
        customer_id="CUS-0007",
        session_id="session-001",
        verified=False,
    )

    with pytest.raises(IdentityVerificationError):
        service.assess_eligibility(
            unverified_identity,
            **assessment_arguments,
        )

    customer_repository.get_by_reference.assert_not_called()
    audit_repository.record.assert_not_called()


def test_rejects_inactive_customer(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, audit_repository = repositories
    customer.is_active = False
    customer_repository.get_by_reference.return_value = customer

    with pytest.raises(CustomerMismatchError):
        service.assess_eligibility(
            identity,
            **assessment_arguments,
        )

    audit_repository.record.assert_not_called()


def test_returns_not_eligible_without_active_account(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, _ = repositories
    customer_repository.get_by_reference.return_value = customer
    customer.accounts = [
        SimpleNamespace(status="BLOCKED"),
        SimpleNamespace(status="CLOSED"),
    ]

    result = service.assess_eligibility(
        identity,
        **assessment_arguments,
    )

    assert result.result == NOT_ELIGIBLE_UNDER_CURRENT_RULES
    assert result.reason_codes == ("NO_ACTIVE_ACCOUNT",)


def test_returns_not_eligible_for_unsupported_employment_type(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, _ = repositories
    customer_repository.get_by_reference.return_value = customer

    customer.loan_eligibility_profile.employment_type = "SELF_EMPLOYED"

    result = service.assess_eligibility(
        identity,
        **assessment_arguments,
    )

    assert result.result == NOT_ELIGIBLE_UNDER_CURRENT_RULES
    assert "EMPLOYMENT_TYPE_NOT_SUPPORTED" in result.reason_codes


def test_audit_does_not_store_customer_financial_values(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, audit_repository = repositories
    customer_repository.get_by_reference.return_value = customer

    service.assess_eligibility(
        identity,
        **assessment_arguments,
    )

    event = audit_repository.record.call_args.args[0]

    assert "monthly_income" not in event.details
    assert "monthly_expenses" not in event.details
    assert "existing_monthly_debt" not in event.details


def test_accepts_financial_profile_verified_exactly_90_days_ago(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, _ = repositories
    customer_repository.get_by_reference.return_value = customer

    assessment_time = assessment_arguments["now"]
    customer.loan_eligibility_profile.verified_at = (
        assessment_time - timedelta(days=90)
    )

    result = service.assess_eligibility(
        identity,
        **assessment_arguments,
    )

    assert result.result == ELIGIBLE_FOR_REVIEW


def test_returns_insufficient_data_for_stale_financial_profile(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, _ = repositories
    customer_repository.get_by_reference.return_value = customer

    assessment_time = assessment_arguments["now"]
    customer.loan_eligibility_profile.verified_at = (
        assessment_time - timedelta(days=90, seconds=1)
    )

    result = service.assess_eligibility(
        identity,
        **assessment_arguments,
    )

    assert result.result == INSUFFICIENT_DATA
    assert result.reason_codes == ("FINANCIAL_PROFILE_STALE",)


def test_returns_insufficient_data_when_verification_timestamp_is_missing(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, _ = repositories
    customer_repository.get_by_reference.return_value = customer

    customer.loan_eligibility_profile.verified_at = None

    result = service.assess_eligibility(
        identity,
        **assessment_arguments,
    )

    assert result.result == INSUFFICIENT_DATA
    assert result.reason_codes == (
        "FINANCIAL_PROFILE_VERIFICATION_TIMESTAMP_MISSING",
    )


def test_returns_insufficient_data_for_future_verification_timestamp(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, _ = repositories
    customer_repository.get_by_reference.return_value = customer

    assessment_time = assessment_arguments["now"]
    customer.loan_eligibility_profile.verified_at = (
        assessment_time + timedelta(seconds=1)
    )

    result = service.assess_eligibility(
        identity,
        **assessment_arguments,
    )

    assert result.result == INSUFFICIENT_DATA
    assert result.reason_codes == (
        "FINANCIAL_PROFILE_VERIFICATION_TIMESTAMP_IN_FUTURE",
    )


def test_returns_insufficient_data_for_naive_verification_timestamp(
    service: LoanEligibilityService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Mock,
    assessment_arguments: dict,
) -> None:
    customer_repository, _ = repositories
    customer_repository.get_by_reference.return_value = customer

    customer.loan_eligibility_profile.verified_at = datetime(
        2026, 10, 1, 10, 0
    )

    result = service.assess_eligibility(
        identity,
        **assessment_arguments,
    )

    assert result.result == INSUFFICIENT_DATA
    assert result.reason_codes == (
        "FINANCIAL_PROFILE_VERIFICATION_TIMESTAMP_INVALID",
    )


def test_rejects_naive_assessment_timestamp(
    service: LoanEligibilityService,
    assessment_arguments: dict,
) -> None:
    assessment_arguments["now"] = datetime(2026, 11, 1, 10, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        service.assess_eligibility(
            CustomerIdentity(
                customer_id="CUS-0007",
                session_id="session-001",
                verified=True,
            ),
            **assessment_arguments,
        )


def test_rejects_invalid_requested_amount(
    service: LoanEligibilityService,
    identity: CustomerIdentity,
    assessment_arguments: dict,
) -> None:
    assessment_arguments["requested_amount"] = Decimal("0")

    with pytest.raises(ValueError, match="greater than zero"):
        service.assess_eligibility(
            identity,
            **assessment_arguments,
        )


def test_rejects_invalid_term(
    service: LoanEligibilityService,
    identity: CustomerIdentity,
    assessment_arguments: dict,
) -> None:
    assessment_arguments["term_months"] = 0

    with pytest.raises(ValueError, match="greater than zero"):
        service.assess_eligibility(
            identity,
            **assessment_arguments,
        )
