"""Audit event contract for security-sensitive application actions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Structured description of an action and its outcome."""

    event_id: str
    occurred_at: datetime
    actor_id: str
    action: str
    outcome: str
    correlation_id: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "event_id",
            "actor_id",
            "action",
            "outcome",
            "correlation_id",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")

        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
