"""Contracts for approval of sensitive actions."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ConfirmationStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


@dataclass(frozen=True, slots=True)
class ConfirmationRequest:
    """Description of an action requiring explicit customer approval."""

    confirmation_id: str
    customer_id: str
    action: str
    created_at: datetime
    expires_at: datetime
    status: ConfirmationStatus = ConfirmationStatus.PENDING

    def __post_init__(self) -> None:
        for field_name in (
            "confirmation_id",
            "customer_id",
            "action",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")

        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")

        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("expires_at must be timezone-aware")

        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")
