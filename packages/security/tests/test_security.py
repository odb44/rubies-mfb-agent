from datetime import UTC, datetime, timedelta

import pytest
from rubies_security import (
    BankingAction,
    ConfirmationAlreadyConsumedError,
    ConfirmationExpiredError,
    ConfirmationRequiredError,
    CustomerMismatchError,
    IdentityVerificationError,
    InMemoryConfirmationStore,
    require_allowed_action,
    require_customer_match,
    require_verified_identity,
)
from rubies_shared import (
    ConfirmationRequest,
    ConfirmationStatus,
    CustomerIdentity,
)


@pytest.fixture
def verified_identity() -> CustomerIdentity:
    return CustomerIdentity(
        customer_id="CUS-0001",
        session_id="SESSION-001",
        verified=True,
    )


@pytest.fixture
def unverified_identity() -> CustomerIdentity:
    return CustomerIdentity(
        customer_id="CUS-0001",
        session_id="SESSION-001",
        verified=False,
    )


def make_confirmation(
    *,
    status: ConfirmationStatus = ConfirmationStatus.APPROVED,
    customer_id: str = "CUS-0001",
    action: str = "block_card",
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> ConfirmationRequest:
    now = datetime.now(UTC)

    return ConfirmationRequest(
        confirmation_id="CONF-001",
        customer_id=customer_id,
        action=action,
        created_at=created_at or now - timedelta(minutes=1),
        expires_at=expires_at or now + timedelta(minutes=5),
        status=status,
    )


def test_missing_identity_is_rejected() -> None:
    with pytest.raises(IdentityVerificationError):
        require_verified_identity(None)


def test_unverified_identity_is_rejected(
    unverified_identity: CustomerIdentity,
) -> None:
    with pytest.raises(IdentityVerificationError):
        require_verified_identity(unverified_identity)


def test_matching_customer_is_allowed(
    verified_identity: CustomerIdentity,
) -> None:
    require_customer_match(verified_identity, "CUS-0001")


def test_cross_customer_access_is_rejected(
    verified_identity: CustomerIdentity,
) -> None:
    with pytest.raises(CustomerMismatchError):
        require_customer_match(verified_identity, "CUS-0002")


def test_allowed_action_requires_verified_identity(
    unverified_identity: CustomerIdentity,
) -> None:
    with pytest.raises(IdentityVerificationError):
        require_allowed_action(unverified_identity, BankingAction.GET_BALANCE)


def test_unrecognized_action_is_rejected(
    verified_identity: CustomerIdentity,
) -> None:
    with pytest.raises(ValueError):
        require_allowed_action(verified_identity, "transfer_money")  # type: ignore[arg-type]


def test_valid_confirmation_can_be_consumed(
    verified_identity: CustomerIdentity,
) -> None:
    store = InMemoryConfirmationStore()
    request = make_confirmation()
    store.add(request)

    consumed = store.consume(
        confirmation_id=request.confirmation_id,
        identity=verified_identity,
        action="block_card",
    )

    assert consumed.confirmation_id == "CONF-001"


def test_confirmation_cannot_be_consumed_twice(
    verified_identity: CustomerIdentity,
) -> None:
    store = InMemoryConfirmationStore()
    request = make_confirmation()
    store.add(request)

    store.consume(
        confirmation_id=request.confirmation_id,
        identity=verified_identity,
        action="block_card",
    )

    with pytest.raises(ConfirmationAlreadyConsumedError):
        store.consume(
            confirmation_id=request.confirmation_id,
            identity=verified_identity,
            action="block_card",
        )


def test_pending_confirmation_is_rejected(
    verified_identity: CustomerIdentity,
) -> None:
    store = InMemoryConfirmationStore()
    request = make_confirmation(status=ConfirmationStatus.PENDING)
    store.add(request)

    with pytest.raises(ConfirmationRequiredError):
        store.consume(
            confirmation_id=request.confirmation_id,
            identity=verified_identity,
            action="block_card",
        )


def test_confirmation_for_another_customer_is_rejected(
    verified_identity: CustomerIdentity,
) -> None:
    store = InMemoryConfirmationStore()
    request = make_confirmation(customer_id="CUS-0002")
    store.add(request)

    with pytest.raises(CustomerMismatchError):
        store.consume(
            confirmation_id=request.confirmation_id,
            identity=verified_identity,
            action="block_card",
        )


def test_confirmation_for_different_action_is_rejected(
    verified_identity: CustomerIdentity,
) -> None:
    store = InMemoryConfirmationStore()
    request = make_confirmation(action="open_dispute")
    store.add(request)

    with pytest.raises(ConfirmationRequiredError):
        store.consume(
            confirmation_id=request.confirmation_id,
            identity=verified_identity,
            action="block_card",
        )


def test_expired_confirmation_is_rejected(
    verified_identity: CustomerIdentity,
) -> None:
    store = InMemoryConfirmationStore()
    now = datetime.now(UTC)
    request = make_confirmation(
        created_at=now - timedelta(minutes=10),
        expires_at=now - timedelta(minutes=1),
    )
    store.add(request)

    with pytest.raises(ConfirmationExpiredError):
        store.consume(
            confirmation_id=request.confirmation_id,
            identity=verified_identity,
            action="block_card",
            now=now,
        )