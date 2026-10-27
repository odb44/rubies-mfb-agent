"""Standard result contracts for internal tools and services."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ResultStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Outcome returned by a tool or service."""

    status: ResultStatus
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    operation_id: str | None = None

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("message must not be empty")

        if self.status == ResultStatus.SUCCESS and self.error_code is not None:
            raise ValueError("Successful results must not contain an error_code")

        if self.status == ResultStatus.UNKNOWN and not self.operation_id:
            raise ValueError(
                "Unknown outcomes must include an operation_id for reconciliation"
            )
