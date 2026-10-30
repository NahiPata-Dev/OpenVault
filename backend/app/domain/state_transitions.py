from typing import Any

from sqlalchemy.orm import Session

from app.errors import raise_api_error
from app.models import User
from app.services.audit_service import record_event


LEGAL_TRANSITIONS = {
    "request": {
        "DRAFT": {"SUBMITTED"},
        "SUBMITTED": {"INELIGIBLE", "PENDING_REVIEW"},
        "PENDING_REVIEW": {"APPROVED", "REJECTED", "WAITLISTED"},
        "WAITLISTED": {"PENDING_REVIEW", "CANCELLED", "EXPIRED"},
        "APPROVED": {"CANCELLED"},
    },
    "booking": {
        "CONFIRMED": {"CANCELLED", "CHECKED_IN", "NO_SHOW"},
        "NO_SHOW": {"CHECKED_IN"},
        "CHECKED_IN": {"RETURN_PENDING"},
        "RETURN_PENDING": {"CLOSED", "INCIDENT_REVIEW"},
        "INCIDENT_REVIEW": {"CLOSED"},
    },
    "incident": {
        "OPEN": {"INFORMATION_REQUESTED", "UNDER_REVIEW"},
        "INFORMATION_REQUESTED": {"UNDER_REVIEW"},
        "UNDER_REVIEW": {"INFORMATION_REQUESTED", "RESOLVED", "DISMISSED"},
    },
}


def validate_transition(entity_type: str, current_state: str, target_state: str) -> None:
    legal = LEGAL_TRANSITIONS.get(entity_type, {}).get(current_state, set())
    if target_state not in legal:
        raise_api_error(
            "invalid_state",
            f"Cannot transition {entity_type} from {current_state} to {target_state}.",
            409,
        )


def apply_transition(
    session: Session,
    entity: Any,
    entity_type: str,
    target_state: str,
    actor: User | None,
    request_id: str | None = None,
    action: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> Any:
    current_state = entity.status
    validate_transition(entity_type, current_state, target_state)
    entity.status = target_state
    record_event(
        session,
        actor,
        entity_type,
        entity.id,
        action or f"{entity_type}.{target_state.casefold()}",
        request_id,
        before=before or {"status": current_state},
        after=after or {"status": target_state},
        is_demo=entity.is_demo,
    )
    return entity
