from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_session
from app.dependencies import get_current_user, require_roles
from app.domain.allocation import rank_eligible_requests
from app.domain.eligibility import evaluate_eligibility
from app.domain.readiness import active_policy
from app.domain.state_transitions import apply_transition, validate_transition
from app.errors import raise_api_error
from app.models import (
    AccessContract,
    AllocationDecision,
    Booking,
    Notification,
    Resource,
    ResourceRequest,
    User,
)
from app.schemas import DecisionCreate, ResourceRequestCreate
from app.schemas import TrainingRecordCreate
from app.services.audit_service import record_event
from app.services.scope import ensure_resource_write_scope, ensure_same_organization

router = APIRouter(tags=["requests"])
USAGE_DAYS = 30
USAGE_LIMIT_HOURS = 10
ACTIVE_BOOKING_STATES = (
    "CONFIRMED",
    "CHECKED_IN",
    "NO_SHOW",
    "RETURN_PENDING",
    "INCIDENT_REVIEW",
)


@router.post("/api/requests", status_code=201)
def create_request(
    payload: ResourceRequestCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("requester")),
) -> dict:
    key = _validate_idempotency_key(idempotency_key)
    if key:
        existing = session.scalar(
            select(ResourceRequest).where(
                ResourceRequest.requester_id == user.id,
                ResourceRequest.idempotency_key == key,
            )
        )
        if existing:
            if (
                existing.resource_id != str(payload.resource_id)
                or existing.purpose != payload.purpose
                or _as_utc(existing.start_at) != _as_utc(payload.start_at)
                or _as_utc(existing.end_at) != _as_utc(payload.end_at)
            ):
                raise_api_error(
                    "conflict",
                    "The idempotency key was already used with a different request.",
                    409,
                )
            return _request_submission(existing)

    resource = session.get(Resource, str(payload.resource_id))
    if resource is None:
        raise_api_error("not_found", "Resource not found.", 404)
    ensure_same_organization(user, resource)
    start_at, end_at = _as_utc(payload.start_at), _as_utc(payload.end_at)
    result = evaluate_eligibility(
        session, user, resource, start_at, end_at, payload.purpose
    )
    row = ResourceRequest(
        id=str(uuid4()),
        requester_id=user.id,
        resource_id=resource.id,
        purpose=payload.purpose.strip(),
        start_at=start_at,
        end_at=end_at,
        status="DRAFT",
        created_at=datetime.now(timezone.utc),
        idempotency_key=key,
        is_demo=user.is_demo,
    )
    session.add(row)
    session.flush()
    apply_transition(
        session, row, "request", "SUBMITTED", user, request.state.request_id
    )
    target = "INELIGIBLE" if result["blockers"] else "PENDING_REVIEW"
    apply_transition(
        session,
        row,
        "request",
        target,
        None,
        request.state.request_id,
        action="request.ineligible" if target == "INELIGIBLE" else "request.queued_for_review",
        after={"status": target, "blockers": result["blockers"]},
    )
    _commit(session, "The request could not be saved.")
    return _request_submission(row, result)


@router.get("/api/requests/mine")
def my_requests(
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("requester")),
) -> dict:
    _expire_waitlisted(session)
    rows = session.scalars(
        select(ResourceRequest)
        .options(
            joinedload(ResourceRequest.resource),
            joinedload(ResourceRequest.booking).joinedload(Booking.contracts),
            joinedload(ResourceRequest.decisions),
        )
        .where(ResourceRequest.requester_id == user.id)
        .order_by(ResourceRequest.created_at.desc())
    ).unique().all()
    return {
        "items": [_request_history(row) for row in rows],
        "total": len(rows),
    }


@router.get("/api/manager/requests")
def manager_requests(
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("lab_manager")),
) -> dict:
    _expire_waitlisted(session, manager_id=user.id)
    rows = session.scalars(
        select(ResourceRequest)
        .join(Resource)
        .options(joinedload(ResourceRequest.requester), joinedload(ResourceRequest.resource))
        .where(Resource.owner_id == user.id)
        .order_by(ResourceRequest.created_at)
    ).unique().all()
    items = []
    for row in rows:
        eligibility = evaluate_eligibility(
            session,
            row.requester,
            row.resource,
            row.start_at,
            row.end_at,
            row.purpose,
        )
        ranking = _allocation_for_request(session, row)
        items.append(
            {
                "request": _request_read(row),
                "eligibility": {
                    "eligible": not eligibility["blockers"],
                    "blockers": eligibility["blockers"],
                },
                "allocation_recommendation": ranking,
            }
        )
    return {"items": items, "total": len(items)}


@router.post("/api/requests/{request_id}/decision")
def decide_request(
    request_id: str,
    payload: DecisionCreate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("lab_manager")),
) -> dict:
    _lock_resource_decision(session, request_id)
    row = session.scalar(
        select(ResourceRequest)
        .options(joinedload(ResourceRequest.resource), joinedload(ResourceRequest.requester))
        .where(ResourceRequest.id == request_id)
    )
    if row is None:
        raise_api_error("not_found", "Request not found.", 404)
    ensure_resource_write_scope(user, row.resource)
    if row.requester_id == user.id:
        raise_api_error("forbidden", "A requester cannot approve their own request.", 403)

    previous = session.scalar(
        select(AllocationDecision)
        .where(AllocationDecision.request_id == row.id)
        .order_by(AllocationDecision.decision_sequence.desc())
        .limit(1)
    )
    if row.status in {"APPROVED", "REJECTED", "WAITLISTED"} and previous is not None:
        if previous.outcome != payload.outcome or previous.explanation != payload.reason:
            raise_api_error("conflict", "This request already has a different decision.", 409)
        return _decision_response(session, row, previous)
    if row.status != "PENDING_REVIEW":
        validate_transition("request", row.status, "APPROVED")

    policy = active_policy(session, row.resource_id)
    if policy is None:
        raise_api_error(
            "ineligible",
            "This resource cannot be booked because its access policy is missing.",
            422,
            details=[{"code": "policy_missing", "message": "An active policy is required."}],
        )
    eligibility = evaluate_eligibility(
        session,
        row.requester,
        row.resource,
        row.start_at,
        row.end_at,
        row.purpose,
    )
    if eligibility["blockers"]:
        raise_api_error(
            "ineligible",
            "This request is no longer eligible.",
            422,
            details=[
                {"code": blocker["code"], "message": blocker["message"]}
                for blocker in eligibility["blockers"]
            ],
        )

    usage = _usage_for_user(session, row.requester_id, row.resource_id)
    is_over_limit = usage["booked_hours_30d"] + (
        (row.end_at - row.start_at).total_seconds() / 3600
    ) > USAGE_LIMIT_HOURS
    if payload.outcome == "approved" and is_over_limit and not payload.override_reason:
        raise_api_error(
            "ineligible",
            "The requester would exceed the 30-day usage limit.",
            422,
            details=[{"code": "usage_limit", "message": "A manager override reason is required."}],
        )

    if payload.outcome == "approved":
        _ensure_no_overlap(session, row)
    allocation = _allocation_for_request(session, row)
    snapshot = {
        **allocation["inputs_snapshot"],
        "request": {
            "request_id": row.id,
            "resource_id": row.resource_id,
            "requester_id": row.requester_id,
            "purpose": row.purpose,
            "start_at": row.start_at.isoformat(),
            "end_at": row.end_at.isoformat(),
        },
        "policy": {
            "id": policy.id,
            "version": policy.version,
            "priority_policy": policy.priority_policy,
        },
        "eligibility": {
            "eligible": not eligibility["blockers"],
            "blocker_codes": [item["code"] for item in eligibility["blockers"]],
        },
        "maintenance_status": row.resource.status,
        "supervised_windows": policy.structured_requirements.get(
            "supervised_windows", []
        ),
        "usage": usage,
        "reviewer_id": user.id,
        "outcome": payload.outcome,
        "override_reason": payload.override_reason,
        "decision_at": datetime.now(timezone.utc).isoformat(),
    }
    sequence = (previous.decision_sequence + 1) if previous else 1
    explanation = _explanation(row, user, payload.outcome, payload.reason)
    decision = AllocationDecision(
        id=str(uuid4()),
        request_id=row.id,
        decision_sequence=sequence,
        policy_version=policy.id,
        outcome=payload.outcome,
        explanation_code=allocation["recommendation"],
        explanation=explanation,
        inputs_snapshot=snapshot,
        reviewer_override=(
            {"reason": payload.override_reason} if payload.override_reason else None
        ),
        reviewer_id=user.id,
        created_at=datetime.now(timezone.utc),
        is_demo=row.is_demo,
    )
    session.add(decision)
    target = payload.outcome.upper()
    apply_transition(
        session,
        row,
        "request",
        target,
        user,
        request.state.request_id,
        action=f"request.{payload.outcome}",
        before={"status": "PENDING_REVIEW"},
        after={"status": target, "reason": payload.reason},
    )
    booking = None
    contract = None
    if payload.outcome == "approved":
        booking = Booking(
            id=str(uuid4()),
            request_id=row.id,
            start_at=row.start_at,
            end_at=row.end_at,
            status="CONFIRMED",
            approved_by=user.id,
            version=1,
            is_demo=row.is_demo,
        )
        session.add(booking)
        session.flush()
        contract = AccessContract(
            id=str(uuid4()),
            booking_id=booking.id,
            version=1,
            request_id=row.id,
            resource_id=row.resource_id,
            requester_id=row.requester_id,
            approver_id=user.id,
            start_at=row.start_at,
            end_at=row.end_at,
            approved_purpose=row.purpose,
            policy_version_id=policy.id,
            requirements_snapshot=policy.structured_requirements,
            supervision_requirement=policy.structured_requirements.get(
                "supervisor_required", False
            ),
            permitted_use=policy.allowed_uses,
            checkin_required=True,
            checkout_required=True,
            condition_checklist_version="northstar-condition-v1",
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            approved_at=datetime.now(timezone.utc),
            expires_at=row.end_at,
            is_demo=row.is_demo,
        )
        session.add(contract)
        record_event(
            session,
            user,
            "booking",
            booking.id,
            "booking.confirmed",
            request.state.request_id,
            after={"status": "CONFIRMED", "request_id": row.id},
            is_demo=row.is_demo,
        )
    _notify(session, row.requester_id, "decision", "resource_request", row.id, row.is_demo)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_api_error("conflict", "The request could not be decided due to a conflict.", 409)
    return {
        "decision": _decision_read(decision),
        "request": _request_read(row),
        "booking": _booking_read(booking) if booking else None,
        "access_contract": _contract_read(contract) if contract else None,
    }


@router.post("/api/requests/{request_id}/cancel")
def cancel_request(
    request_id: str,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    row = session.scalar(
        select(ResourceRequest)
        .options(joinedload(ResourceRequest.resource), joinedload(ResourceRequest.booking))
        .where(ResourceRequest.id == request_id)
    )
    if row is None:
        raise_api_error("not_found", "Request not found.", 404)
    if user.role == "requester":
        if row.requester_id != user.id:
            raise_api_error("forbidden", "You can cancel only your own request.", 403)
    elif user.role == "lab_manager":
        ensure_resource_write_scope(user, row.resource)
    else:
        raise_api_error("forbidden", "You are not authorized to cancel this request.", 403)
    if row.status == "APPROVED":
        cutoff = _as_utc(row.start_at) - timedelta(hours=2)
        if datetime.now(timezone.utc) > cutoff:
            raise_api_error("invalid_state", "Cancellation is closed less than two hours before start.", 409)
    apply_transition(
        session,
        row,
        "request",
        "CANCELLED",
        user,
        request.state.request_id,
        action="request.cancelled",
    )
    if row.booking is not None:
        apply_transition(
            session,
            row.booking,
            "booking",
            "CANCELLED",
            user,
            request.state.request_id,
            action="booking.cancelled",
        )
        for contract in row.booking.contracts:
            contract.status = "CANCELLED"
    _notify(session, row.requester_id, "cancellation", "resource_request", row.id, row.is_demo)
    _commit(session, "The request could not be cancelled.")
    return {"request": _request_read(row)}


@router.post("/api/requests/{request_id}/promote")
def promote_waitlist(
    request_id: str,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("lab_manager")),
) -> dict:
    row = session.scalar(
        select(ResourceRequest)
        .options(joinedload(ResourceRequest.resource), joinedload(ResourceRequest.requester))
        .where(ResourceRequest.id == request_id)
    )
    if row is None:
        raise_api_error("not_found", "Request not found.", 404)
    ensure_resource_write_scope(user, row.resource)
    validate_transition("request", row.status, "PENDING_REVIEW")
    eligibility = evaluate_eligibility(
        session, row.requester, row.resource, row.start_at, row.end_at, row.purpose
    )
    if eligibility["blockers"]:
        raise_api_error(
            "ineligible",
            "This waitlisted request is no longer eligible.",
            422,
            details=[
                {"code": item["code"], "message": item["message"]}
                for item in eligibility["blockers"]
            ],
        )
    apply_transition(
        session,
        row,
        "request",
        "PENDING_REVIEW",
        user,
        request.state.request_id,
        action="request.promoted_to_review",
    )
    _notify(session, row.requester_id, "waitlist_promotion", "resource_request", row.id, row.is_demo)
    _commit(session, "The waitlisted request could not be promoted.")
    return {"request": _request_read(row), "eligibility": {"eligible": True, "blockers": []}}


@router.post("/api/training-records", status_code=201)
def create_training_record(
    payload: TrainingRecordCreate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("lab_manager")),
) -> dict:
    from app.models import TrainingRecord
    subject = session.get(User, str(payload.user_id))
    if subject is None or subject.organization_id != user.organization_id:
        raise_api_error("not_found", "User not found.", 404)
    row = TrainingRecord(
        id=str(uuid4()),
        user_id=subject.id,
        requirement_code=payload.requirement_code,
        status=payload.status,
        verified_by=user.id,
        valid_from=_as_utc(payload.valid_from),
        valid_to=_as_utc(payload.valid_to) if payload.valid_to else None,
        is_demo=subject.is_demo,
    )
    session.add(row)
    record_event(
        session,
        user,
        "training_record",
        row.id,
        "training_record.created",
        request.state.request_id,
        after={"user_id": subject.id, "requirement_code": row.requirement_code, "status": row.status},
        is_demo=row.is_demo,
    )
    _commit(session, "The training record could not be saved.")
    return {"training_record": _training_read(row)}


def _lock_resource_decision(session: Session, request_id: str) -> None:
    resource_id = session.scalar(
        select(ResourceRequest.resource_id).where(ResourceRequest.id == request_id)
    )
    if resource_id is None:
        return
    bind = session.get_bind()
    if bind.dialect.name == "sqlite":
        session.rollback()
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    elif bind.dialect.name == "postgresql":
        session.execute(
            select(Resource.id).where(Resource.id == resource_id).with_for_update()
        ).scalar_one()


def _ensure_no_overlap(session: Session, row: ResourceRequest) -> None:
    conflict = session.scalar(
        select(Booking.id)
        .join(ResourceRequest, ResourceRequest.id == Booking.request_id)
        .where(
            ResourceRequest.resource_id == row.resource_id,
            Booking.status.in_(ACTIVE_BOOKING_STATES),
            Booking.start_at < row.end_at,
            Booking.end_at > row.start_at,
        )
        .limit(1)
    )
    if conflict:
        raise_api_error(
            "conflict",
            "Another confirmed booking overlaps this interval.",
            409,
        )


def _allocation_for_request(session: Session, row: ResourceRequest) -> dict:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=USAGE_DAYS)
    competing = session.scalars(
        select(ResourceRequest)
        .where(
            ResourceRequest.resource_id == row.resource_id,
            ResourceRequest.status == "PENDING_REVIEW",
            ResourceRequest.start_at < row.end_at,
            ResourceRequest.end_at > row.start_at,
        )
        .order_by(ResourceRequest.created_at, ResourceRequest.id)
    ).all()
    if row not in competing:
        competing.append(row)
    candidates = []
    for contender in competing:
        usage = _usage_for_user(
            session, contender.requester_id, contender.resource_id, start, end
        )
        candidates.append(
            {
                "request_id": contender.id,
                "requester_id": contender.requester_id,
                "created_at": contender.created_at,
                **usage,
            }
        )
    return rank_eligible_requests(candidates, now=end)


def _usage_for_user(
    session: Session,
    requester_id: str,
    resource_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict:
    end = _as_utc(end or datetime.now(timezone.utc))
    start = _as_utc(start or (end - timedelta(days=USAGE_DAYS)))
    rows = session.execute(
        select(Booking.start_at, Booking.end_at, Booking.status)
        .join(ResourceRequest, ResourceRequest.id == Booking.request_id)
        .where(
            ResourceRequest.requester_id == requester_id,
            ResourceRequest.resource_id == resource_id,
            Booking.status != "CANCELLED",
            Booking.start_at >= start,
            Booking.start_at < end,
        )
    ).all()
    hours = sum(
        (_as_utc(booking_end) - _as_utc(booking_start)).total_seconds() / 3600
        for booking_start, booking_end, _status in rows
    )
    completed = sum(1 for _start, _end, status in rows if status == "CLOSED")
    return {"completed_bookings_30d": completed, "booked_hours_30d": hours}


def _expire_waitlisted(session: Session, manager_id: str | None = None) -> None:
    now = datetime.now(timezone.utc)
    query = select(ResourceRequest).where(
        ResourceRequest.status == "WAITLISTED",
        ResourceRequest.start_at <= now,
    )
    if manager_id:
        query = query.join(Resource).where(Resource.owner_id == manager_id)
    rows = session.scalars(query).all()
    for row in rows:
        apply_transition(
            session,
            row,
            "request",
            "EXPIRED",
            None,
            action="request.expired",
        )
    if rows:
        session.commit()


def _request_submission(row: ResourceRequest, eligibility: dict | None = None) -> dict:
    if eligibility is None:
        eligibility = {"ready": row.status != "INELIGIBLE", "blockers": []}
    return {
        "request": _request_read(row),
        "eligibility": {
            "eligible": not eligibility["blockers"],
            "blockers": eligibility["blockers"],
        },
    }


def _request_read(row: ResourceRequest) -> dict:
    return {
        "id": row.id,
        "requester_id": row.requester_id,
        "resource_id": row.resource_id,
        "purpose": row.purpose,
        "start_at": _as_utc(row.start_at).isoformat(),
        "end_at": _as_utc(row.end_at).isoformat(),
        "status": row.status,
        "created_at": _as_utc(row.created_at).isoformat(),
        "is_demo": row.is_demo,
    }


def _request_history(row: ResourceRequest) -> dict:
    decision = max(row.decisions, key=lambda item: item.decision_sequence, default=None)
    booking = row.booking
    contract = max(booking.contracts, key=lambda item: item.version, default=None) if booking else None
    return {
        "request": _request_read(row),
        "decision": _decision_read(decision) if decision else None,
        "booking": _booking_read(booking) if booking else None,
        "access_contract": _contract_read(contract) if contract else None,
    }


def _decision_response(session: Session, row: ResourceRequest, decision: AllocationDecision) -> dict:
    session.refresh(row)
    return {
        "decision": _decision_read(decision),
        "request": _request_read(row),
        "booking": _booking_read(row.booking) if row.booking else None,
        "access_contract": (
            _contract_read(row.booking.contracts[-1]) if row.booking and row.booking.contracts else None
        ),
    }


def _decision_read(row: AllocationDecision | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row.id,
        "request_id": row.request_id,
        "decision_sequence": row.decision_sequence,
        "outcome": row.outcome,
        "explanation_code": row.explanation_code,
        "explanation": row.explanation,
        "reviewer_id": row.reviewer_id,
        "created_at": _as_utc(row.created_at).isoformat(),
    }


def _booking_read(row: Booking | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row.id,
        "request_id": row.request_id,
        "start_at": _as_utc(row.start_at).isoformat(),
        "end_at": _as_utc(row.end_at).isoformat(),
        "status": row.status,
        "approved_by": row.approved_by,
        "version": row.version,
    }


def _contract_read(row: AccessContract | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row.id,
        "booking_id": row.booking_id,
        "version": row.version,
        "request_id": row.request_id,
        "resource_id": row.resource_id,
        "requester_id": row.requester_id,
        "approver_id": row.approver_id,
        "start_at": _as_utc(row.start_at).isoformat(),
        "end_at": _as_utc(row.end_at).isoformat(),
        "approved_purpose": row.approved_purpose,
        "policy_version_id": row.policy_version_id,
        "requirements_snapshot": row.requirements_snapshot,
        "status": row.status,
        "expires_at": _as_utc(row.expires_at).isoformat(),
    }


def _training_read(row) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "requirement_code": row.requirement_code,
        "status": row.status,
        "verified_by": row.verified_by,
        "valid_from": _as_utc(row.valid_from).isoformat(),
        "valid_to": _as_utc(row.valid_to).isoformat() if row.valid_to else None,
        "is_demo": row.is_demo,
    }


def _explanation(row: ResourceRequest, reviewer: User, outcome: str, reason: str) -> str:
    start_at = _as_utc(row.start_at).isoformat()
    end_at = _as_utc(row.end_at).isoformat()
    if outcome == "approved":
        return (
            f"Your request for {row.resource.name} from {start_at} to {end_at} "
            f"was approved by {reviewer.display_name}. Reason: {reason} "
            "Access Contract (session conditions) is available for this booking."
        )
    if outcome == "rejected":
        return (
            f"Your request for {row.resource.name} from {start_at} to {end_at} "
            f"was not approved. Reason: {reason}"
        )
    return (
        f"Your request for {row.resource.name} from {start_at} to {end_at} "
        f"is waitlisted. Reason: {reason} No booking is confirmed; "
        "you will be notified if it moves to review."
    )


def _notify(
    session: Session,
    recipient_id: str,
    notification_type: str,
    entity_type: str,
    entity_id: str,
    is_demo: bool,
) -> None:
    existing = session.scalar(
        select(Notification.id).where(
            Notification.recipient_id == recipient_id,
            Notification.type == notification_type,
            Notification.related_entity_type == entity_type,
            Notification.related_entity_id == entity_id,
        )
    )
    if existing is None:
        session.add(
            Notification(
                id=str(uuid4()),
                recipient_id=recipient_id,
                type=notification_type,
                related_entity_type=entity_type,
                related_entity_id=entity_id,
                read_at=None,
                created_at=datetime.now(timezone.utc),
                is_demo=is_demo,
            )
        )


def _validate_idempotency_key(value: str | None) -> str | None:
    if value is not None and (not value.strip() or len(value) > 160):
        raise_api_error("validation_error", "Idempotency-Key must be 1-160 characters.", 422)
    return value.strip() if value else None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _commit(session: Session, message: str) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_api_error("conflict", message, 409)
