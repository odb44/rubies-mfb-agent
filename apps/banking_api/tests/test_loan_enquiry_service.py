"""Tests for customer identity and ownership in loan enquiries."""

from unittest.mock import Mock

import pytest
from rubies_banking_api.models.customer import Customer
from rubies_banking_api.services.loan_enquiry_service import (
    LoanEnquiryService,
)
from rubies_security.identity import (
    CustomerMismatchError,
    IdentityVerificationError,
)
from rubies_shared.identity import CustomerIdentity


@pytest.fixture
def customer() -> Customer:
    return Customer(
        id=7,
        customer_reference="CUS-0007",
        full_name="Demo Customer",
        is_active=True,
    )


@pytest.fixture
def identity() -> CustomerIdentity:
    return CustomerIdentity(
        customer_id="CUS-0007",
        session_id="session-001",
        verified=True,
    )


@pytest.fixture
def repositories() -> tuple[Mock, Mock, Mock]:
    loan_repository = Mock()
    loan_application_repository = Mock()
    customer_repository = Mock()

    return (
        loan_repository,
        loan_application_repository,
        customer_repository,
    )


@pytest.fixture
def service(
    repositories: tuple[Mock, Mock, Mock],
) -> LoanEnquiryService:
    (
        loan_repository,
        loan_application_repository,
        customer_repository,
    ) = repositories

    return LoanEnquiryService(
        loan_repository=loan_repository,
        loan_application_repository=loan_application_repository,
        customer_repository=customer_repository,
    )


@pytest.fixture
def owned_loan(customer: Customer) -> Mock:
    application = Mock()
    application.customer_id = customer.id

    loan = Mock()
    loan.reference = "LOAN-001"
    loan.customer_id = customer.id
    loan.application = application

    return loan


def test_returns_loan_owned_by_verified_customer(
    service: LoanEnquiryService,
    repositories: tuple[Mock, Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
    owned_loan: Mock,
) -> None:
    loan_repository, _, customer_repository = repositories
    customer_repository.get_by_reference.return_value = customer
    loan_repository.get_by_reference.return_value = owned_loan

    result = service.get_loan_status(
        identity,
        loan_reference="LOAN-001",
    )

    assert result is owned_loan
    customer_repository.get_by_reference.assert_called_once_with(
        "CUS-0007"
    )
    loan_repository.get_by_reference.assert_called_once_with("LOAN-001")


def test_rejects_unverified_identity(
    service: LoanEnquiryService,
    repositories: tuple[Mock, Mock, Mock],
) -> None:
    loan_repository, _, customer_repository = repositories

    unverified_identity = CustomerIdentity(
        customer_id="CUS-0007",
        session_id="session-001",
        verified=False,
    )

    with pytest.raises(IdentityVerificationError):
        service.get_loan_status(
            unverified_identity,
            loan_reference="LOAN-001",
        )

    customer_repository.get_by_reference.assert_not_called()
    loan_repository.get_by_reference.assert_not_called()


def test_rejects_unknown_customer(
    service: LoanEnquiryService,
    repositories: tuple[Mock, Mock, Mock],
    identity: CustomerIdentity,
) -> None:
    loan_repository, _, customer_repository = repositories
    customer_repository.get_by_reference.return_value = None

    with pytest.raises(CustomerMismatchError):
        service.get_loan_status(
            identity,
            loan_reference="LOAN-001",
        )

    loan_repository.get_by_reference.assert_not_called()


def test_rejects_inactive_customer(
    service: LoanEnquiryService,
    repositories: tuple[Mock, Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
) -> None:
    loan_repository, _, customer_repository = repositories
    customer.is_active = False
    customer_repository.get_by_reference.return_value = customer

    with pytest.raises(CustomerMismatchError):
        service.get_loan_status(
            identity,
            loan_reference="LOAN-001",
        )

    loan_repository.get_by_reference.assert_not_called()


def test_rejects_another_customers_loan(
    service: LoanEnquiryService,
    repositories: tuple[Mock, Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
    owned_loan: Mock,
) -> None:
    loan_repository, _, customer_repository = repositories
    customer_repository.get_by_reference.return_value = customer

    owned_loan.customer_id = 99
    loan_repository.get_by_reference.return_value = owned_loan

    with pytest.raises(CustomerMismatchError):
        service.get_loan_status(
            identity,
            loan_reference="LOAN-OTHER",
        )


def test_rejects_loan_linked_to_another_customers_application(
    service: LoanEnquiryService,
    repositories: tuple[Mock, Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
    owned_loan: Mock,
) -> None:
    loan_repository, _, customer_repository = repositories
    customer_repository.get_by_reference.return_value = customer

    # The loan itself belongs to this customer, but its linked
    # application belongs to someone else.
    owned_loan.application.customer_id = 99
    loan_repository.get_by_reference.return_value = owned_loan

    with pytest.raises(CustomerMismatchError):
        service.get_loan_status(
            identity,
            loan_reference="LOAN-001",
        )


def test_rejects_another_customers_loan_application(
    service: LoanEnquiryService,
    repositories: tuple[Mock, Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
) -> None:
    _, application_repository, customer_repository = repositories

    customer_repository.get_by_reference.return_value = customer

    other_customers_application = Mock()
    other_customers_application.customer_id = 99
    application_repository.get_by_reference.return_value = (
        other_customers_application
    )

    with pytest.raises(CustomerMismatchError):
        service.get_loan_application_status(
            identity,
            application_reference="APP-OTHER",
        )

    application_repository.get_by_reference.assert_called_once_with(
        "APP-OTHER"
    )


def test_rejects_unknown_loan(
    service: LoanEnquiryService,
    repositories: tuple[Mock, Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
) -> None:
    loan_repository, _, customer_repository = repositories
    customer_repository.get_by_reference.return_value = customer
    loan_repository.get_by_reference.return_value = None

    with pytest.raises(ValueError, match="Loan not found"):
        service.get_loan_status(
            identity,
            loan_reference="LOAN-MISSING",
        )


def test_rejects_unknown_loan_application(
    service: LoanEnquiryService,
    repositories: tuple[Mock, Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
) -> None:
    _, application_repository, customer_repository = repositories
    customer_repository.get_by_reference.return_value = customer
    application_repository.get_by_reference.return_value = None

    with pytest.raises(ValueError, match="Loan application not found"):
        service.get_loan_application_status(
            identity,
            application_reference="APP-MISSING",
        )