from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_session
from app.dependencies import require_roles
from app.models import (
    Booking,
    Incident,
    Resource,
    ResourceRequest,
    TrainingRecord,
    User,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
EXPIRY_WINDOW = timedelta(days=30)


@router.get("/requester")
def requester_dashboard(
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("requester")),
) -> dict:
    now = datetime.now(timezone.utc)
    upcoming = session.scalars(
        select(Booking)
        .join(ResourceRequest)
        .options(joinedload(Booking.request).joinedload(ResourceRequest.resource))
        .where(
            ResourceRequest.requester_id == user.id,
            Booking.status.in_(("CONFIRMED", "CHECKED_IN", "NO_SHOW")),
            Booking.end_at >= now,
        )
        .order_by(Booking.start_at)
    ).unique().all()
    pending = session.scalars(
        select(ResourceRequest)
        .options(joinedload(ResourceRequest.resource))
        .where(
            ResourceRequest.requester_id == user.id,
            ResourceRequest.status.in_(("PENDING_REVIEW", "WAITLISTED")),
        )
        .order_by(ResourceRequest.start_at)
    ).all()
    incidents = session.scalars(
        select(Incident)
        .join(Booking)
        .join(ResourceRequest)
        .options(
            joinedload(Incident.booking)
            .joinedload(Booking.request)
            .joinedload(ResourceRequest.resource)
        )
        .where(
            ResourceRequest.requester_id == user.id,
            Incident.status.not_in(("RESOLVED", "DISMISSED")),
        )
        .order_by(Incident.created_at.desc())
    ).unique().all()
    expiring_training = session.scalars(
        select(TrainingRecord)
        .where(
            TrainingRecord.user_id == user.id,
            TrainingRecord.status == "valid",
            TrainingRecord.valid_to.is_not(None),
            TrainingRecord.valid_to > now,
            TrainingRecord.valid_to <= now + EXPIRY_WINDOW,
        )
        .order_by(TrainingRecord.valid_to)
    ).all()
    next_items = [
        _booking_item(row) for row in upcoming
    ] + [
        _request_item(row) for row in pending
    ] + [
        _incident_item(row, row.booking.request.resource.name) for row in incidents
    ] + [
        _training_item(row) for row in expiring_training
    ]
    return {
        "summary": {
            "upcoming_bookings": len(upcoming),
            "pending_requests": len(pending),
            "open_incidents": len(incidents),
            "expiring_training": len(expiring_training),
        },
        "next_items": _next_five(next_items),
    }


@router.get("/manager")
def manager_dashboard(
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("lab_manager")),
) -> dict:
    now = datetime.now(timezone.utc)
    managed_resource_ids = select(Resource.id).where(Resource.owner_id == user.id)
    upcoming = session.scalars(
        select(Booking)
        .join(ResourceRequest)
        .join(Resource)
        .options(joinedload(Booking.request).joinedload(ResourceRequest.resource))
        .where(
            Resource.owner_id == user.id,
            Booking.status.in_(("CONFIRMED", "CHECKED_IN", "NO_SHOW")),
            Booking.end_at >= now,
        )
        .order_by(Booking.start_at)
    ).unique().all()
    pending = session.scalars(
        select(ResourceRequest)
        .join(Resource)
        .options(joinedload(ResourceRequest.resource))
        .where(
            Resource.owner_id == user.id,
            ResourceRequest.status.in_(("PENDING_REVIEW", "WAITLISTED")),
        )
        .order_by(ResourceRequest.start_at)
    ).unique().all()
    incidents = session.scalars(
        select(Incident)
        .join(Booking)
        .join(ResourceRequest)
        .options(
            joinedload(Incident.booking)
            .joinedload(Booking.request)
            .joinedload(ResourceRequest.resource)
        )
        .where(
            ResourceRequest.resource_id.in_(managed_resource_ids),
            Incident.status.not_in(("RESOLVED", "DISMISSED")),
        )
        .order_by(Incident.created_at.desc())
    ).unique().all()
    expiring_training = session.scalars(
        select(TrainingRecord)
        .join(User, TrainingRecord.user_id == User.id)
        .where(
            User.organization_id == user.organization_id,
            TrainingRecord.status == "valid",
            TrainingRecord.valid_to.is_not(None),
            TrainingRecord.valid_to > now,
            TrainingRecord.valid_to <= now + EXPIRY_WINDOW,
        )
        .order_by(TrainingRecord.valid_to)
    ).all()
    next_items = [
        _booking_item(row) for row in upcoming
    ] + [
        _request_item(row) for row in pending
    ] + [
        _incident_item(row, row.booking.request.resource.name) for row in incidents
    ] + [
        _training_item(row) for row in expiring_training
    ]
    return {
        "summary": {
            "upcoming_bookings": len(upcoming),
            "pending_requests": len(pending),
            "open_incidents": len(incidents),
            "expiring_training": len(expiring_training),
        },
        "next_items": _next_five(next_items),
    }


def _booking_item(booking: Booking) -> dict:
    return {
        "type": "upcoming_booking",
        "id": booking.id,
        "title": f"Booking: {booking.request.resource.name}",
        "at": _utc(booking.start_at),
        "status": booking.status,
    }


def _request_item(row: ResourceRequest) -> dict:
    return {
        "type": "pending_request",
        "id": row.id,
        "title": f"Request: {row.resource.name}",
        "at": _utc(row.start_at),
        "status": row.status,
    }


def _incident_item(row: Incident, resource_name: str) -> dict:
    return {
        "type": "open_incident",
        "id": row.id,
        "title": f"Incident: {resource_name}",
        "at": _utc(row.created_at),
        "status": row.status,
    }


def _training_item(row: TrainingRecord) -> dict:
    return {
        "type": "expiring_training",
        "id": row.id,
        "title": f"Training expires: {row.requirement_code}",
        "at": _utc(row.valid_to) if row.valid_to else None,
        "status": row.status,
    }


def _next_five(items: list[dict]) -> list[dict]:
    return sorted(
        items,
        key=lambda item: (
            item["at"] is None,
            item["at"].timestamp() if item["at"] is not None else float("inf"),
            item["type"],
            item["id"],
        ),
    )[:5]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
