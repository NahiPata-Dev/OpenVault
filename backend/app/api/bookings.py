from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_session
from app.dependencies import require_roles
from app.domain.eligibility import evaluate_eligibility
from app.domain.state_transitions import apply_transition, validate_transition
from app.errors import raise_api_error
from app.models import (
    AccessContract,
    Booking,
    HandoverReport,
    Incident,
    Resource,
    ResourceRequest,
    User,
)
from app.schemas import HandoverCreate
from app.services.audit_service import record_event

router = APIRouter(prefix="/api/bookings", tags=["bookings"])
CHECKLIST_VERSION = "northstar-condition-v1"
CHECKIN_LEAD = timedelta(minutes=15)
NO_SHOW_AFTER = timedelta(minutes=30)


@router.post("/{booking_id}/check-in")
def check_in(
    booking_id: str,
    payload: HandoverCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("requester")),
) -> dict:
    booking = _booking(session, booking_id)
    if booking.request.requester_id != user.id:
        raise_api_error("forbidden", "Only the booking requester may check in.", 403)
    existing = _find_idempotent_report(
        session, booking, "IN", user, idempotency_key, payload
    )
    if existing is not None:
        return {"booking": _booking_read(booking), "handover_report": _report_read(existing)}
    if payload.checklist_version != CHECKLIST_VERSION:
        raise_api_error("validation_error", "Unsupported checklist version.", 422)

    now = datetime.now(timezone.utc)
    start_at, end_at = _as_utc(booking.start_at), _as_utc(booking.end_at)
    if now < start_at - CHECKIN_LEAD or now >= end_at:
        raise_api_error("invalid_state", "The check-in window is closed.", 409)
    if booking.status not in {"CONFIRMED", "NO_SHOW"}:
        validate_transition("booking", booking.status, "CHECKED_IN")
    if session.scalar(
        select(HandoverReport.id).where(
            HandoverReport.booking_id == booking.id,
            HandoverReport.stage == "IN",
        )
    ):
        raise_api_error("invalid_state", "This booking already has a check-in report.", 409)

    resource = booking.request.resource
    eligibility = evaluate_eligibility(
        session,
        user,
        resource,
        start_at,
        end_at,
        booking.request.purpose,
        exclude_booking_id=booking.id,
    )
    if eligibility["blockers"]:
        raise_api_error(
            "ineligible",
            "This booking is no longer eligible for check-in.",
            422,
            details=[
                {"code": item["code"], "message": item["message"]}
                for item in eligibility["blockers"]
            ],
        )

    if booking.status == "CONFIRMED" and now >= start_at + NO_SHOW_AFTER:
        apply_transition(
            session,
            booking,
            "booking",
            "NO_SHOW",
            None,
            request.state.request_id,
            action="booking.no_show",
        )
    target_action = (
        "booking.late_checked_in" if booking.status == "NO_SHOW" else "booking.checked_in"
    )
    apply_transition(
        session,
        booking,
        "booking",
        "CHECKED_IN",
        user,
        request.state.request_id,
        action=target_action,
    )
    report = _new_report(booking, user, "IN", payload, idempotency_key)
    session.add(report)
    _commit(session, "The check-in could not be recorded.")
    return {"booking": _booking_read(booking), "handover_report": _report_read(report)}


@router.post("/{booking_id}/check-out")
def check_out(
    booking_id: str,
    payload: HandoverCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("requester")),
) -> dict:
    booking = _booking(session, booking_id)
    if booking.request.requester_id != user.id:
        raise_api_error("forbidden", "Only the booking requester may check out.", 403)
    existing = _find_idempotent_report(
        session, booking, "OUT", user, idempotency_key, payload
    )
    if existing is not None:
        incident = session.scalar(
            select(Incident).where(Incident.booking_id == booking.id).order_by(Incident.created_at.desc())
        )
        return {
            "booking": _booking_read(booking),
            "handover_report": _report_read(existing),
            "incident": _incident_read(incident) if incident else None,
        }
    if payload.checklist_version != CHECKLIST_VERSION:
        raise_api_error("validation_error", "Unsupported checklist version.", 422)
    if booking.status != "CHECKED_IN":
        validate_transition("booking", booking.status, "RETURN_PENDING")
    incoming = session.scalar(
        select(HandoverReport).where(
            HandoverReport.booking_id == booking.id,
            HandoverReport.stage == "IN",
        )
    )
    if incoming is None:
        raise_api_error("invalid_state", "Check-out requires a recorded check-in.", 409)
    if session.scalar(
        select(HandoverReport.id).where(
            HandoverReport.booking_id == booking.id,
            HandoverReport.stage == "OUT",
        )
    ):
        raise_api_error("invalid_state", "This booking already has a check-out report.", 409)

    report = _new_report(booking, user, "OUT", payload, idempotency_key)
    session.add(report)
    apply_transition(
        session,
        booking,
        "booking",
        "RETURN_PENDING",
        user,
        request.state.request_id,
        action="booking.checked_out",
    )
    categories = _discrepancy_categories(incoming.condition, payload.condition.model_dump())
    incident = None
    if categories:
        category = categories[0] if len(categories) == 1 else "other"
        incident = Incident(
            id=str(uuid4()),
            booking_id=booking.id,
            reporter_id=user.id,
            category=category,
            description=_discrepancy_description(categories),
            status="OPEN",
            responses=[],
            resolution=None,
            reviewer_id=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            is_demo=booking.is_demo,
        )
        session.add(incident)
        session.flush()
        record_event(
            session,
            user,
            "incident",
            incident.id,
            "incident.opened",
            request.state.request_id,
            after={"booking_id": booking.id, "category": category, "status": "OPEN"},
            is_demo=incident.is_demo,
        )
        apply_transition(
            session,
            booking,
            "booking",
            "INCIDENT_REVIEW",
            None,
            request.state.request_id,
            action="booking.incident_review_opened",
        )
    else:
        apply_transition(
            session,
            booking,
            "booking",
            "CLOSED",
            None,
            request.state.request_id,
            action="booking.closed",
        )
        _set_contract_status(session, booking, "COMPLETED")
    _commit(session, "The check-out could not be recorded.")
    return {
        "booking": _booking_read(booking),
        "handover_report": _report_read(report),
        "incident": _incident_read(incident) if incident else None,
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


def _find_idempotent_report(
    session: Session,
    booking: Booking,
    stage: str,
    user: User,
    key: str | None,
    payload: HandoverCreate,
) -> HandoverReport | None:
    if key is not None and (not key.strip() or len(key) > 160):
        raise_api_error("validation_error", "Idempotency-Key must be 1-160 characters.", 422)
    if key is None:
        return None
    report = session.scalar(
        select(HandoverReport).where(
            HandoverReport.actor_id == user.id,
            HandoverReport.idempotency_key == key,
        )
    )
    if report is None:
        return None
    supplied_condition = payload.condition.model_dump()
    supplied_evidence = [item.model_dump() for item in payload.evidence_references]
    if (
        report.booking_id != booking.id
        or report.stage != stage
        or report.checklist_version != payload.checklist_version
        or report.condition != supplied_condition
        or report.evidence_references != supplied_evidence
    ):
        raise_api_error("conflict", "The idempotency key was reused with a different payload.", 409)
    return report


def _new_report(
    booking: Booking,
    user: User,
    stage: str,
    payload: HandoverCreate,
    key: str | None,
) -> HandoverReport:
    condition = payload.condition.model_dump()
    return HandoverReport(
        id=str(uuid4()),
        booking_id=booking.id,
        stage=stage,
        checklist_version=payload.checklist_version,
        condition=condition,
        notes=condition.get("notes"),
        evidence_references=[item.model_dump() for item in payload.evidence_references],
        actor_id=user.id,
        created_at=datetime.now(timezone.utc),
        idempotency_key=key,
        is_demo=booking.is_demo,
    )


def _discrepancy_categories(before: dict, after: dict) -> list[str]:
    condition_rank = {"ok": 0, "minor_wear": 1, "damaged": 2}
    categories = []
    if condition_rank[after["physical_condition"]] > condition_rank[before["physical_condition"]]:
        categories.append("damage")
    if after["accessories_complete"] == "no":
        categories.append("missing_part")
    if after["functional_test"] == "issue":
        categories.append("malfunction")
    return categories


def _discrepancy_description(categories: list[str]) -> str:
    labels = {
        "damage": "physical condition changed",
        "missing_part": "accessories are incomplete",
        "malfunction": "functional test reported an issue",
    }
    return "Return checklist review requested: " + "; ".join(labels[item] for item in categories) + "."


def _set_contract_status(session: Session, booking: Booking, status: str) -> None:
    for contract in booking.contracts:
        contract.status = status


def _booking_read(row: Booking) -> dict:
    return {
        "id": row.id,
        "request_id": row.request_id,
        "start_at": _as_utc(row.start_at).isoformat(),
        "end_at": _as_utc(row.end_at).isoformat(),
        "status": row.status,
        "approved_by": row.approved_by,
        "version": row.version,
    }


def _report_read(row: HandoverReport) -> dict:
    return {
        "id": row.id,
        "booking_id": row.booking_id,
        "stage": row.stage,
        "checklist_version": row.checklist_version,
        "condition": row.condition,
        "notes": row.notes,
        "evidence_references": row.evidence_references,
        "actor_id": row.actor_id,
        "created_at": _as_utc(row.created_at).isoformat(),
    }


def _incident_read(row: Incident) -> dict:
    return {
        "id": row.id,
        "booking_id": row.booking_id,
        "reporter_id": row.reporter_id,
        "category": row.category,
        "description": row.description,
        "status": row.status,
        "responses": row.responses,
        "resolution": row.resolution,
        "reviewer_id": row.reviewer_id,
    }


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _commit(session: Session, message: str) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_api_error("conflict", message, 409)
