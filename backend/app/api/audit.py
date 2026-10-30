from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.dependencies import get_current_user
from app.errors import raise_api_error
from app.models import (
    AccessContract,
    AuditEvent,
    Booking,
    HandoverReport,
    Incident,
    Resource,
    ResourcePolicy,
    ResourceRequest,
    User,
)
from app.services.scope import ensure_resource_write_scope, ensure_same_organization

router = APIRouter(tags=["audit"])


@router.get("/api/audit")
def list_audit(
    entity_type: str | None = None,
    entity_id: str | None = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    visible_ids = _visible_entity_ids(session, user)
    query = select(AuditEvent).where(AuditEvent.entity_id.in_(visible_ids))
    if entity_type:
        query = query.where(AuditEvent.entity_type == entity_type)
    if entity_id:
        if entity_id not in visible_ids:
            raise_api_error("not_found", "Audit records not found.", 404)
        query = query.where(AuditEvent.entity_id == entity_id)
    events = session.scalars(query.order_by(AuditEvent.timestamp.desc()).limit(500)).all()
    return {"items": [_event_read(event) for event in events], "total": len(events)}


@router.get("/api/resources/{resource_id}/timeline")
def resource_timeline(
    resource_id: str,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    resource = session.get(Resource, resource_id)
    if resource is None:
        raise_api_error("not_found", "Resource not found.", 404)
    ensure_same_organization(user, resource)
    if user.role == "lab_manager":
        ensure_resource_write_scope(user, resource)
    if from_time and to_time and to_time <= from_time:
        raise_api_error("validation_error", "The requested date range is invalid.", 422)
    ids = _resource_entity_ids(session, [resource.id])
    query = select(AuditEvent).where(AuditEvent.entity_id.in_(ids))
    if from_time:
        query = query.where(AuditEvent.timestamp >= from_time)
    if to_time:
        query = query.where(AuditEvent.timestamp <= to_time)
    events = session.scalars(query.order_by(AuditEvent.timestamp.asc()).limit(500)).all()
    return {
        "items": [
            {
                "timestamp": _event_read(event)["timestamp"],
                "event": event.action,
                "actor": _actor_name(session, event.actor_id),
                "summary": event.after_summary or event.before_summary or {},
            }
            for event in events
        ]
    }


def _visible_entity_ids(session: Session, user: User) -> list[str]:
    if user.role in {"institution_admin", "auditor"}:
        resources = session.scalars(
            select(Resource.id).where(Resource.owner.has(organization_id=user.organization_id))
        ).all()
        return _resource_entity_ids(session, resources)
    if user.role == "lab_manager":
        resources = session.scalars(
            select(Resource.id).where(Resource.owner_id == user.id)
        ).all()
        return _resource_entity_ids(session, resources)
    requests = session.scalars(
        select(ResourceRequest.id).where(ResourceRequest.requester_id == user.id)
    ).all()
    ids = set(requests)
    bookings = session.scalars(
        select(Booking.id).where(Booking.request_id.in_(requests))
    ).all() if requests else []
    ids.update(bookings)
    ids.update(
        session.scalars(
            select(Incident.id).where(Incident.booking_id.in_(bookings))
        ).all() if bookings else []
    )
    ids.update(
        session.scalars(
            select(HandoverReport.id).where(HandoverReport.booking_id.in_(bookings))
        ).all() if bookings else []
    )
    return list(ids)


def _resource_entity_ids(session: Session, resource_ids: list[str]) -> list[str]:
    if not resource_ids:
        return []
    request_ids = session.scalars(
        select(ResourceRequest.id).where(ResourceRequest.resource_id.in_(resource_ids))
    ).all()
    policy_ids = session.scalars(
        select(ResourcePolicy.id).where(ResourcePolicy.resource_id.in_(resource_ids))
    ).all()
    booking_ids = session.scalars(
        select(Booking.id).where(Booking.request_id.in_(request_ids))
    ).all() if request_ids else []
    contract_ids = session.scalars(
        select(AccessContract.id).where(AccessContract.booking_id.in_(booking_ids))
    ).all() if booking_ids else []
    incident_ids = session.scalars(
        select(Incident.id).where(Incident.booking_id.in_(booking_ids))
    ).all() if booking_ids else []
    handover_ids = session.scalars(
        select(HandoverReport.id).where(HandoverReport.booking_id.in_(booking_ids))
    ).all() if booking_ids else []
    return list(set(resource_ids + request_ids + policy_ids + booking_ids + contract_ids + incident_ids + handover_ids))


def _event_read(event: AuditEvent) -> dict:
    return {
        "id": event.id,
        "actor_id": event.actor_id,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "action": event.action,
        "timestamp": event.timestamp.isoformat(),
        "before_summary": event.before_summary,
        "after_summary": event.after_summary,
    }


def _actor_name(session: Session, actor_id: str | None) -> str | None:
    if actor_id is None:
        return None
    actor = session.get(User, actor_id)
    return actor.display_name if actor else None
