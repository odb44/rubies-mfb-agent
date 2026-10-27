from unittest.mock import Mock

import pytest
from rubies_banking_api.models.customer import Customer
from rubies_banking_api.services.dispute_service import DisputeService
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
def repositories() -> tuple[Mock, Mock]:
    dispute_repository = Mock()
    customer_repository = Mock()
    return dispute_repository, customer_repository


@pytest.fixture
def service(repositories: tuple[Mock, Mock]) -> DisputeService:
    dispute_repository, customer_repository = repositories

    return DisputeService(
        dispute_repository=dispute_repository,
        customer_repository=customer_repository,
        confirmation_repository=Mock(),
        audit_repository=Mock(),
    )


def test_resolves_customer_reference(
    service: DisputeService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
) -> None:
    _, customer_repository = repositories
    customer_repository.get_by_reference.return_value = customer

    result = service.resolve_customer(identity)

    assert result.id == 7
    assert result.customer_reference == "CUS-0007"
    customer_repository.get_by_reference.assert_called_once_with("CUS-0007")


def test_rejects_unverified_identity(
    service: DisputeService,
    repositories: tuple[Mock, Mock],
) -> None:
    dispute_repository, customer_repository = repositories
    unverified_identity = CustomerIdentity(
        customer_id="CUS-0007",
        session_id="session-001",
        verified=False,
    )

    with pytest.raises(IdentityVerificationError):
        service.resolve_customer(unverified_identity)

    customer_repository.get_by_reference.assert_not_called()
    dispute_repository.add.assert_not_called()


def test_rejects_unknown_customer(
    service: DisputeService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
) -> None:
    _, customer_repository = repositories
    customer_repository.get_by_reference.return_value = None

    with pytest.raises(CustomerMismatchError):
        service.resolve_customer(identity)


def test_rejects_inactive_customer(
    service: DisputeService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
) -> None:
    _, customer_repository = repositories
    customer.is_active = False
    customer_repository.get_by_reference.return_value = customer

    with pytest.raises(CustomerMismatchError, match="not active"):
        service.resolve_customer(identity)


def test_accepts_valid_dispute_request(
    service: DisputeService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
) -> None:
    _, customer_repository = repositories
    customer_repository.get_by_reference.return_value = customer

    result = service.validate_request(
        identity,
        category="duplicate_debit",
        description="Customer reports a duplicate debit.",
    )

    assert result.id == 7


def test_rejects_invalid_category(
    service: DisputeService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
) -> None:
    _, customer_repository = repositories
    customer_repository.get_by_reference.return_value = customer

    with pytest.raises(ValueError, match="Unsupported dispute category"):
        service.validate_request(
            identity,
            category="INVALID_CATEGORY",
            description="Customer reports a duplicate debit.",
        )


def test_rejects_blank_description(
    service: DisputeService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
) -> None:
    _, customer_repository = repositories
    customer_repository.get_by_reference.return_value = customer

    with pytest.raises(ValueError, match="description is required"):
        service.validate_request(
            identity,
            category="DUPLICATE_DEBIT",
            description="   ",
        )


def test_rejects_another_customers_transaction(
    service: DisputeService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
) -> None:
    _, customer_repository = repositories
    customer_repository.get_by_reference.return_value = customer

    transaction = Mock()
    transaction.account.customer_id = 8

    with pytest.raises(
        CustomerMismatchError,
        match="does not belong to this customer",
    ):
        service.validate_request(
            identity,
            category="DUPLICATE_DEBIT",
            description="Customer reports a duplicate debit.",
            transaction=transaction,
        )


def test_does_not_create_dispute_during_validation(
    service: DisputeService,
    repositories: tuple[Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
) -> None:
    dispute_repository, customer_repository = repositories
    customer_repository.get_by_reference.return_value = customer

    service.validate_request(
        identity,
        category="DUPLICATE_DEBIT",
        description="Customer reports a duplicate debit.",
    )

    dispute_repository.add.assert_not_called()