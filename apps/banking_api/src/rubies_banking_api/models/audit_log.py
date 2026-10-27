"""Persistent audit records for sensitive banking operations."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from rubies_banking_api.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("ix_audit_logs_actor_occurred_at", "actor_id", "occurred_at"),
        Index("ix_audit_logs_correlation_id", "correlation_id"),
        Index("ix_audit_logs_action_outcome", "action", "outcome"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    event_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    actor_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    outcome: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    correlation_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default="{}",
    )