"""Persistence for security-sensitive audit events."""

from rubies_shared.audit import AuditEvent
from sqlalchemy.orm import Session

from rubies_banking_api.models.audit_log import AuditLog


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(self, event: AuditEvent) -> AuditLog:
        audit_log = AuditLog(
            event_id=event.event_id,
            occurred_at=event.occurred_at,
            actor_id=event.actor_id,
            action=event.action,
            outcome=event.outcome,
            correlation_id=event.correlation_id,
            details=event.details,
        )
        self.db.add(audit_log)
        self.db.flush()
        return audit_log