from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_session
from app.dependencies import get_current_user, require_roles
from app.domain.state_transitions import apply_transition, validate_transition
from app.errors import raise_api_error
from app.models import AccessContract, Booking, Incident, Resource, ResourceRequest, User
from app.schemas import (
    IncidentCreate,
    IncidentResolve,
    IncidentResponseCreate,
    IncidentReview,
)
from app.services.audit_service import record_event
from app.services.scope import ensure_resource_write_scope

router = APIRouter(tags=["incidents"])
ACTIVE_INCIDENT_STATES = {"OPEN", "INFORMATION_REQUESTED", "UNDER_REVIEW"}


@router.post("/api/bookings/{booking_id}/incidents", status_code=201)
def create_incident(
    booking_id: str,
    payload: IncidentCreate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    booking = _booking(session, booking_id)
    if user.role == "requester":
        if booking.request.requester_id != user.id:
            raise_api_error("forbidden", "You can report only on your own booking.", 403)
    elif user.role == "lab_manager":
        ensure_resource_write_scope(user, booking.request.resource)
    else:
        raise_api_error("forbidden", "You are not authorized to report this incident.", 403)
    if booking.status not in {"CHECKED_IN", "RETURN_PENDING", "INCIDENT_REVIEW"}:
        raise_api_error("invalid_state", "An incident requires an active booking.", 409)

    now = datetime.now(timezone.utc)
    incident = Incident(
        id=str(uuid4()),
        booking_id=booking.id,
        reporter_id=user.id,
        category=payload.category,
        description=payload.description.strip(),
        status="OPEN",
        responses=[],
        resolution=None,
        reviewer_id=None,
        created_at=now,
        updated_at=now,
        is_demo=booking.is_demo,
    )
    session.add(incident)
    record_event(
        session,
        user,
        "incident",
        incident.id,
        "incident.opened",
        request.state.request_id,
        after={"booking_id": booking.id, "category": incident.category, "status": "OPEN"},
        is_demo=incident.is_demo,
    )
    _commit(session, "The incident could not be saved.")
    return {"incident": _incident_read(incident)}


@router.get("/api/incidents/{incident_id}")
def get_incident(
    incident_id: str,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    incident = _incident(session, incident_id)
    _ensure_incident_scope(user, incident)
    return {
        "incident": _incident_read(incident),
        "booking": {
            "id": incident.booking.id,
            "request_id": incident.booking.request_id,
            "status": incident.booking.status,
        },
    }


@router.post("/api/incidents/{incident_id}/responses", status_code=201)
def respond_to_incident(
    incident_id: str,
    payload: IncidentResponseCreate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    if user.role not in {"requester", "lab_manager"}:
        raise_api_error("forbidden", "Only the requester or scoped manager may respond.", 403)
    incident = _incident(session, incident_id)
    _ensure_incident_scope(user, incident, allow_manager=True)
    if incident.status not in ACTIVE_INCIDENT_STATES:
        raise_api_error("invalid_state", "A response cannot be added to a terminal incident.", 409)
    incident.responses = [
        *incident.responses,
        {
            "actor_id": user.id,
            "message": payload.message.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    incident.updated_at = datetime.now(timezone.utc)
    record_event(
        session,
        user,
        "incident",
        incident.id,
        "incident.response_added",
        request.state.request_id,
        after={"response_count": len(incident.responses)},
        is_demo=incident.is_demo,
    )
    _commit(session, "The incident response could not be saved.")
    return {"incident": _incident_read(incident)}


@router.post("/api/incidents/{incident_id}/review")
def review_incident(
    incident_id: str,
    payload: IncidentReview,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("lab_manager")),
) -> dict:
    incident = _incident(session, incident_id)
    ensure_resource_write_scope(user, incident.booking.request.resource)
    target = payload.status.upper()
    action = (
        "incident.information_requested"
        if target == "INFORMATION_REQUESTED"
        else "incident.review_started"
    )
    apply_transition(
        session,
        incident,
        "incident",
        target,
        user,
        request.state.request_id,
        action=action,
        after={"status": target, "reason": payload.reason},
    )
    incident.updated_at = datetime.now(timezone.utc)
    _commit(session, "The incident review could not be recorded.")
    return {"incident": _incident_read(incident)}


@router.post("/api/incidents/{incident_id}/resolve")
def resolve_incident(
    incident_id: str,
    payload: IncidentResolve,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("lab_manager")),
) -> dict:
    incident = _incident(session, incident_id)
    ensure_resource_write_scope(user, incident.booking.request.resource)
    target = payload.outcome.upper()
    event = apply_transition(
        session,
        incident,
        "incident",
        target,
        user,
        request.state.request_id,
        action=f"incident.{payload.outcome}",
        after={"status": target, "rationale": payload.rationale},
    )
    incident.resolution = {
        "outcome": payload.outcome,
        "rationale": payload.rationale.strip(),
        "resolved_by": user.id,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }
    incident.reviewer_id = user.id
    incident.updated_at = datetime.now(timezone.utc)
    booking = incident.booking
    if booking.status == "INCIDENT_REVIEW":
        apply_transition(
            session,
            booking,
            "booking",
            "CLOSED",
            user,
            request.state.request_id,
            action="booking.closed_after_review",
        )
        for contract in booking.contracts:
            contract.status = "COMPLETED"
    _commit(session, "The incident resolution could not be saved.")
    return {
        "incident": _incident_read(incident),
        "audit_event_id": event.id,
    }


def _booking(session: Session, booking_id: str) -> Booking:
    booking = session.scalar(
        select(Booking)
        .options(
            joinedload(Booking.request).joinedload(ResourceRequest.requester),
            joinedload(Booking.request).joinedload(ResourceRequest.resource),
            joinedload(Booking.contracts),
        )
        .where(Booking.id == booking_id)
    )
    if booking is None:
        raise_api_error("not_found", "Booking not found.", 404)
    return booking


def _incident(session: Session, incident_id: str) -> Incident:
    incident = session.scalar(
        select(Incident)
        .options(
            joinedload(Incident.booking)
            .joinedload(Booking.request)
            .joinedload(ResourceRequest.resource),
            joinedload(Incident.booking)
            .joinedload(Booking.request)
            .joinedload(ResourceRequest.requester),
        )
        .where(Incident.id == incident_id)
    )
    if incident is None:
        raise_api_error("not_found", "Incident not found.", 404)
    return incident


def _ensure_incident_scope(
    user: User,
    incident: Incident,
    allow_manager: bool = False,
) -> None:
    request = incident.booking.request
    if user.role == "requester":
        if request.requester_id != user.id:
            raise_api_error("not_found", "Incident not found.", 404)
        return
    if user.role == "lab_manager":
        ensure_resource_write_scope(user, request.resource)
        return
    if user.role in {"institution_admin", "auditor"}:
        if request.resource.owner.organization_id != user.organization_id:
            raise_api_error("not_found", "Incident not found.", 404)
        return
    raise_api_error("forbidden", "You are not authorized to view this incident.", 403)


def _incident_read(incident: Incident) -> dict:
    return {
        "id": incident.id,
        "booking_id": incident.booking_id,
        "reporter_id": incident.reporter_id,
        "category": incident.category,
        "description": incident.description,
        "status": incident.status,
        "responses": incident.responses,
        "resolution": incident.resolution,
        "reviewer_id": incident.reviewer_id,
        "created_at": _as_utc(incident.created_at).isoformat(),
        "updated_at": _as_utc(incident.updated_at).isoformat(),
        "is_demo": incident.is_demo,
    }


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _commit(session: Session, message: str) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_api_error("conflict", message, 409)
