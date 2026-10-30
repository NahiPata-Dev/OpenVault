from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import AuditEvent, User


def record_event(
    session: Session,
    actor: User | None,
    entity_type: str,
    entity_id: str,
    action: str,
    request_id: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    is_demo: bool = True,
) -> AuditEvent:
    event = AuditEvent(
        id=str(uuid4()),
        actor_id=actor.id if actor else None,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        timestamp=datetime.now(timezone.utc),
        request_id=request_id,
        correlation_id=request_id,
        before_summary=before,
        after_summary=after,
        is_demo=is_demo,
    )
    session.add(event)
    return event
