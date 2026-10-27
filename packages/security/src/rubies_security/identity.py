"""Security checks for trusted customer identity."""

from rubies_shared import CustomerIdentity


class SecurityError(Exception):
    """Base exception for security failures."""


class IdentityVerificationError(SecurityError):
    """Raised when trusted identity is missing or unverified."""


class CustomerMismatchError(SecurityError):
    """Raised when an operation targets a different customer."""


def require_verified_identity(identity: CustomerIdentity | None) -> CustomerIdentity:
    """Require an authenticated identity that has completed verification."""

    if identity is None:
        raise IdentityVerificationError("A trusted customer identity is required.")

    if not identity.verified:
        raise IdentityVerificationError("Customer verification is required.")

    return identity


def require_customer_match(
    identity: CustomerIdentity,
    requested_customer_id: str,
) -> None:
    """Prevent a caller from accessing another customer's records."""

    require_verified_identity(identity)

    if not requested_customer_id.strip():
        raise CustomerMismatchError("A customer ID is required.")

    if identity.customer_id != requested_customer_id:
        raise CustomerMismatchError("The requested customer does not match the session.")
