"""Trusted identity context supplied by the application security layer."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CustomerIdentity:
    """Identity established by trusted authentication middleware."""

    customer_id: str
    session_id: str
    verified: bool

    def __post_init__(self) -> None:
        if not self.customer_id.strip():
            raise ValueError("customer_id must not be empty")
        if not self.session_id.strip():
            raise ValueError("session_id must not be empty")
