from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from rubies_security.identity import (
    CustomerMismatchError,
    IdentityVerificationError,
)
from rubies_shared.identity import CustomerIdentity
from rubies_banking_api.services.transaction_enquiry_service import (
    TransactionEnquiryService,
)


@pytest.fixture
def customer():
    return SimpleNamespace(
        id=7,
        customer_reference="CUS-0007",
        is_active=True,
    )


@pytest.fixture
def identity():
    return CustomerIdentity(
        customer_id="CUS-0007",
        session_id="session-001",
        verified=True,
    )


@pytest.fixture
def repositories():
    return {
        "transaction": Mock(),
        "customer": Mock(),
    }


@pytest.fixture
def service(repositories):
    return TransactionEnquiryService(
        transaction_repository=repositories["transaction"],
        customer_repository=repositories["customer"],
    )


@pytest.fixture
def owned_account(customer):
    return SimpleNamespace(
        id=11,
        customer_id=customer.id,
        account_number="0123456789",
        status="ACTIVE",
    )


@pytest.fixture
def owned_transaction(owned_account):
    return SimpleNamespace(
        id=101,
        reference="TXN-001",
        account=owned_account,
    )


def test_returns_transaction_owned_by_verified_customer(
    service,
    repositories,
    customer,
    identity,
    owned_transaction,
):
    repositories["customer"].get_by_reference.return_value = customer
    repositories["transaction"].get_by_reference.return_value = (
        owned_transaction
    )

    result = service.get_transaction_status(
        identity,
        transaction_reference="TXN-001",
    )

    assert result is owned_transaction


def test_rejects_unverified_identity(
    service,
    repositories,
):
    identity = CustomerIdentity(
        customer_id="CUS-0007",
        session_id="session-001",
        verified=False,
    )

    with pytest.raises(IdentityVerificationError):
        service.get_transaction_status(
            identity,
            transaction_reference="TXN-001",
        )

    repositories["customer"].get_by_reference.assert_not_called()
    repositories["transaction"].get_by_reference.assert_not_called()


def test_rejects_unknown_customer(
    service,
    repositories,
    identity,
):
    repositories["customer"].get_by_reference.return_value = None

    with pytest.raises(CustomerMismatchError):
        service.get_transaction_status(
            identity,
            transaction_reference="TXN-001",
        )

    repositories["transaction"].get_by_reference.assert_not_called()


def test_rejects_inactive_customer(
    service,
    repositories,
    identity,
    customer,
):
    customer.is_active = False
    repositories["customer"].get_by_reference.return_value = customer

    with pytest.raises(CustomerMismatchError):
        service.get_transaction_status(
            identity,
            transaction_reference="TXN-001",
        )

    repositories["transaction"].get_by_reference.assert_not_called()


def test_rejects_another_customers_transaction(
    service,
    repositories,
    customer,
    identity,
    owned_transaction,
):
    repositories["customer"].get_by_reference.return_value = customer

    other_account = SimpleNamespace(
        id=22,
        customer_id=99,
        account_number="9876543210",
        status="ACTIVE",
    )
    foreign_transaction = SimpleNamespace(
        id=202,
        reference="TXN-FOREIGN",
        account=other_account,
    )
    repositories["transaction"].get_by_reference.return_value = (
        foreign_transaction
    )

    with pytest.raises(CustomerMismatchError):
        service.get_transaction_status(
            identity,
            transaction_reference="TXN-FOREIGN",
        )


def test_rejects_unknown_transaction(
    service,
    repositories,
    customer,
    identity,
):
    repositories["customer"].get_by_reference.return_value = customer
    repositories["transaction"].get_by_reference.return_value = None

    with pytest.raises(ValueError, match="Transaction not found"):
        service.get_transaction_status(
            identity,
            transaction_reference="TXN-MISSING",
        )


def test_returns_mini_statement_for_owned_account(
    service,
    repositories,
    customer,
    identity,
    owned_account,
):
    repositories["customer"].get_by_reference.return_value = customer
    repositories["transaction"].get_account_by_number.return_value = (
        owned_account
    )

    transactions = [
        SimpleNamespace(reference="TXN-001"),
        SimpleNamespace(reference="TXN-002"),
    ]
    repositories["transaction"].list_by_account.return_value = transactions

    account, result = service.get_mini_statement(
        identity,
        account_reference="0123456789",
        limit=10,
        offset=0,
    )

    assert account is owned_account
    assert result == transactions

    repositories["transaction"].list_by_account.assert_called_once_with(
        owned_account.id,
        limit=10,
        offset=0,
    )


def test_rejects_another_customers_account(
    service,
    repositories,
    customer,
    identity,
):
    repositories["customer"].get_by_reference.return_value = customer

    foreign_account = SimpleNamespace(
        id=22,
        customer_id=99,
        account_number="9876543210",
        status="ACTIVE",
    )
    repositories["transaction"].get_account_by_number.return_value = (
        foreign_account
    )

    with pytest.raises(CustomerMismatchError):
        service.get_mini_statement(
            identity,
            account_reference="9876543210",
        )

    repositories["transaction"].list_by_account.assert_not_called()


def test_rejects_inactive_account(
    service,
    repositories,
    customer,
    identity,
    owned_account,
):
    repositories["customer"].get_by_reference.return_value = customer
    owned_account.status = "CLOSED"
    repositories["transaction"].get_account_by_number.return_value = (
        owned_account
    )

    with pytest.raises(ValueError, match="not active"):
        service.get_mini_statement(
            identity,
            account_reference=owned_account.account_number,
        )

    repositories["transaction"].list_by_account.assert_not_called()
