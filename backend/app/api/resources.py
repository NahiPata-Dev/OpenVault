import re
from datetime import datetime, time, timedelta, timezone
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_session
from app.dependencies import get_current_user, require_roles
from app.domain.readiness import ACTIVE_BOOKING_STATES, active_policy, evaluate_readiness
from app.errors import raise_api_error
from app.models import (
    Booking,
    Organization,
    Resource,
    ResourcePolicy,
    ResourceRequest,
    TrainingRecord,
    User,
)
from app.schemas import (
    EligibilityChecklistItem,
    ResourceCreate,
    ResourceListItem,
    ResourceListResponse,
    ResourcePatch,
    ResourcePolicyRead,
    ResourceRead,
    ResourceResponse,
    ReadinessRead,
)
from app.services.audit_service import record_event
from app.services.scope import ensure_resource_write_scope, ensure_same_organization

router = APIRouter(prefix="/api/resources", tags=["resources"])
IST = ZoneInfo("Asia/Kolkata")
DEFAULT_ALLOWED_USES = ["project", "coursework", "research"]


@router.get("", response_model=ResourceListResponse)
def list_resources(
    query: str | None = Query(default=None, max_length=160),
    category: str | None = Query(default=None, max_length=80),
    city: str | None = Query(default=None, max_length=100),
    area: str | None = Query(default=None, max_length=120),
    organization: str | None = Query(default=None, max_length=200),
    status: Literal["active", "maintenance_hold", "retired"] | None = None,
    supervised: bool | None = None,
    training_required: bool | None = None,
    sort: Literal["name", "next_availability"] = "name",
    available_from: datetime | None = None,
    available_to: datetime | None = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ResourceListResponse:
    if (available_from is None) != (available_to is None):
        raise_api_error("validation_error", "available_from and available_to must be provided together.", 422)
    if available_from is not None and (
        available_from.tzinfo is None
        or available_to is None
        or available_to.tzinfo is None
        or available_to <= available_from
    ):
        raise_api_error("validation_error", "The requested interval is invalid.", 422)

    resource_query = (
        select(Resource)
        .options(joinedload(Resource.owner))
        .order_by(Resource.name)
    )
    if user.role == "lab_manager":
        resource_query = resource_query.where(
            Resource.owner.has(organization_id=user.organization_id)
        )
    resources = session.scalars(resource_query).unique().all()
    organizations = {
        row.id: row
        for row in session.scalars(select(Organization)).all()
    }
    needle = query.casefold().strip() if query else None
    results: list[tuple[ResourceListItem, datetime | None]] = []
    for resource in resources:
        policy = active_policy(session, resource.id)
        policy_requirements = policy.structured_requirements if policy else {}
        owner_organization = organizations.get(resource.owner.organization_id)
        resource_supervised = bool(
            policy_requirements.get(
                "supervisor_required", resource.supervision_required
            )
        )
        required_training = _training_names(resource, policy)
        if category and resource.category.casefold() != category.casefold():
            continue
        if city and resource.city.casefold() != city.casefold():
            continue
        if area and resource.area.casefold() != area.casefold():
            continue
        if organization:
            organization_value = organization.casefold().strip()
            organization_fields = (
                resource.owner.organization_id,
                owner_organization.name if owner_organization else "",
            )
            if not any(
                organization_value in value.casefold()
                for value in organization_fields
                if value
            ):
                continue
        if status and resource.status != status:
            continue
        if supervised is not None and resource_supervised != supervised:
            continue
        if training_required is not None and bool(required_training) != training_required:
            continue
        if needle:
            fields = [
                resource.name,
                resource.category,
                resource.short_summary,
                resource.description,
                resource.location,
                resource.city,
                resource.area,
                resource.owner.organization_id,
                owner_organization.name if owner_organization else "",
                resource.building,
                resource.room,
                resource.address_note,
                resource.hold_reason or "",
                resource.condition_notes,
                *resource.capability_tags,
                *resource.who_can_use,
                *resource.required_training,
                *resource.allowed_uses,
                *resource.usage_rules,
                *resource.safety_notes,
                *resource.accessories_included,
                resource.access_model,
            ]
            if not any(needle in field.casefold() for field in fields if field):
                continue
        readiness = evaluate_readiness(
            session, user, resource, available_from, available_to
        )
        next_time = _next_availability(session, resource, policy)
        results.append(
            (
                ResourceListItem(
                    id=resource.id,
                    name=resource.name,
                    category=resource.category,
                    short_summary=resource.short_summary,
                    description=resource.description,
                    capability_tags=resource.capability_tags,
                    location=resource.location,
                    organization_id=resource.owner.organization_id,
                    organization_name=(
                        owner_organization.name
                        if owner_organization
                        else resource.owner.organization_id
                    ),
                    organization_type=(
                        owner_organization.type
                        if owner_organization
                        else "institution"
                    ),
                    city=resource.city,
                    area=resource.area,
                    id_required=resource.id_required,
                    building=resource.building,
                    room=resource.room,
                    capacity=resource.capacity,
                    quantity=resource.quantity,
                    status=resource.status,
                    supervision_required=resource_supervised,
                    required_training=required_training,
                    operating_hours=resource.weekly_operating_hours,
                    weekly_operating_hours=resource.weekly_operating_hours,
                    readiness=ReadinessRead.model_validate(readiness),
                    next_availability=next_time,
                ),
                next_time,
            )
        )
    if sort == "next_availability":
        results.sort(key=lambda result: (result[1] is None, result[1], result[0].name.casefold()))
    else:
        results.sort(key=lambda result: result[0].name.casefold())
    items = [result[0] for result in results]
    return ResourceListResponse(items=items, total=len(items))


@router.get("/{resource_id}", response_model=ResourceResponse)
def get_resource(
    resource_id: str,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    purpose: str | None = Query(default=None, max_length=2000),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ResourceResponse:
    resource = session.scalar(
        select(Resource)
        .options(joinedload(Resource.owner))
        .where(Resource.id == resource_id)
    )
    if resource is None:
        raise_api_error("not_found", "Resource not found.", 404)
    if user.role == "lab_manager":
        ensure_same_organization(user, resource)
    if (start_at is None) != (end_at is None):
        raise_api_error("validation_error", "start_at and end_at must be provided together.", 422)
    if start_at is not None and (
        start_at.tzinfo is None or end_at is None or end_at.tzinfo is None or end_at <= start_at
    ):
        raise_api_error("validation_error", "The requested interval is invalid.", 422)
    policy = active_policy(session, resource.id)
    readiness = evaluate_readiness(session, user, resource, start_at, end_at)
    checklist = _eligibility_checklist(
        session, user, resource, policy, readiness, start_at, end_at, purpose
    )
    return ResourceResponse(
        resource=_resource_read(
            resource,
            policy,
            _organization_profile(session, resource),
        ),
        active_policy=ResourcePolicyRead.model_validate(policy) if policy else None,
        readiness=ReadinessRead.model_validate(readiness),
        eligibility_checklist=checklist,
    )


@router.post("", response_model=ResourceResponse, status_code=201)
def create_resource(
    payload: ResourceCreate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("lab_manager")),
) -> ResourceResponse:
    operating_hours = [item.model_dump() for item in payload.resolved_operating_hours]
    location = payload.location or _location(payload.building, payload.room)
    duration_minutes = payload.max_duration_minutes
    if payload.max_session_hours is not None:
        duration_minutes = round(payload.max_session_hours * 60)
    resource = Resource(
        id=str(uuid4()),
        owner_id=user.id,
        name=payload.name,
        category=payload.category,
        short_summary=payload.short_summary,
        description=payload.description,
        capability_tags=payload.capability_tags,
        location=location,
        city=payload.city,
        area=payload.area,
        id_required=payload.id_required,
        building=payload.building,
        room=payload.room,
        address_note=payload.address_note,
        status=payload.status,
        hold_reason=payload.hold_reason,
        hold_review_date=payload.hold_review_date,
        weekly_operating_hours=operating_hours,
        capacity=payload.capacity,
        quantity=payload.quantity,
        allowed_uses=payload.allowed_uses or [],
        who_can_use=payload.who_can_use,
        required_training=payload.required_training,
        supervision_required=payload.supervision_required,
        supervised_windows=[item.model_dump() for item in payload.supervised_windows],
        usage_rules=payload.usage_rules,
        safety_notes=payload.safety_notes,
        max_session_hours=payload.max_session_hours,
        advance_booking_window=payload.advance_booking_window,
        cancellation_cutoff=payload.cancellation_cutoff,
        accessories_included=payload.accessories_included,
        condition_notes=payload.condition_notes,
        access_model=payload.access_model,
        max_duration_minutes=duration_minutes,
        exclusive_booking=payload.exclusive_booking,
        is_demo=user.is_demo,
    )
    session.add(resource)
    session.flush()
    record_event(
        session,
        user,
        "resource",
        resource.id,
        "resource.created",
        request.state.request_id,
        after={"name": resource.name, "status": resource.status},
        is_demo=resource.is_demo,
    )
    if "allowed_uses" in payload.model_fields_set and payload.allowed_uses:
        if payload.policy_change_reason is None:
            raise_api_error(
                "validation_error",
                "policy_change_reason is required when activating an initial policy.",
                422,
            )
        policy = _new_policy_from_resource(
            resource,
            payload.allowed_uses,
            user,
            1,
            payload.policy_change_reason,
        )
        session.add(policy)
        session.flush()
        record_event(
            session,
            user,
            "resource_policy",
            policy.id,
            "resource_policy.activated",
            request.state.request_id,
            after={
                "resource_id": resource.id,
                "version": policy.version,
                "reason": policy.activation_reason,
            },
            is_demo=policy.is_demo,
        )
    _commit_or_conflict(session, "Resource could not be created.")
    policy = active_policy(session, resource.id)
    return _resource_response(session, user, resource, policy)


@router.patch("/{resource_id}", response_model=ResourceResponse)
def update_resource(
    resource_id: str,
    payload: ResourcePatch,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("lab_manager")),
) -> ResourceResponse:
    resource = session.scalar(
        select(Resource)
        .options(joinedload(Resource.owner))
        .where(Resource.id == resource_id)
    )
    if resource is None:
        raise_api_error("not_found", "Resource not found.", 404)
    ensure_resource_write_scope(user, resource)
    updates = payload.model_dump(exclude_unset=True)
    policy_change_reason = updates.pop("policy_change_reason")
    updates.pop("weekly_operating_hours", None)
    if "operating_hours" in payload.model_fields_set:
        updates["weekly_operating_hours"] = (
            [item.model_dump() for item in payload.operating_hours]
            if payload.operating_hours is not None
            else None
        )
    elif "weekly_operating_hours" in payload.model_fields_set:
        updates["weekly_operating_hours"] = (
            [item.model_dump() for item in payload.weekly_operating_hours]
            if payload.weekly_operating_hours is not None
            else None
        )
    updates.pop("max_duration_minutes", None)
    if "max_session_hours" in payload.model_fields_set:
        updates["max_duration_minutes"] = (
            round(payload.max_session_hours * 60)
            if payload.max_session_hours is not None
            else None
        )
    elif "max_duration_minutes" in payload.model_fields_set:
        updates["max_session_hours"] = (
            payload.max_duration_minutes / 60
            if payload.max_duration_minutes is not None
            else None
        )

    if "capacity" in updates and updates["capacity"] is not None:
        updates["quantity"] = None
    elif "quantity" in updates and updates["quantity"] is not None:
        updates["capacity"] = None
    if "status" in updates:
        status = updates["status"]
        if status == "maintenance_hold":
            resulting_date = updates.get("hold_review_date", resource.hold_review_date)
            resulting_reason = updates.get("hold_reason", resource.hold_reason)
            if resulting_date is None:
                raise_api_error("validation_error", "hold_review_date is required for a maintenance hold.", 422)
            if not resulting_reason:
                raise_api_error("validation_error", "hold_reason is required for a maintenance hold.", 422)
        elif status in {"active", "retired"}:
            updates.setdefault("hold_reason", None)
            updates.setdefault("hold_review_date", None)
    elif resource.status == "maintenance_hold":
        resulting_date = updates.get("hold_review_date", resource.hold_review_date)
        resulting_reason = updates.get("hold_reason", resource.hold_reason)
        if resulting_date is None or not resulting_reason:
            raise_api_error("validation_error", "A maintenance hold requires hold_reason and hold_review_date.", 422)

    if "building" in updates or "room" in updates:
        building = updates.get("building", resource.building)
        room = updates.get("room", resource.room)
        updates.setdefault("location", _location(building, room))
    before = {key: getattr(resource, key) for key in updates}
    for field, value in updates.items():
        if value is not None or field in {
            "hold_reason",
            "hold_review_date",
            "capacity",
            "quantity",
            "max_session_hours",
            "max_duration_minutes",
            "advance_booking_window",
        }:
            setattr(resource, field, value)
    session.flush()

    previous_policy = active_policy(session, resource.id)
    previous_requirements = (
        previous_policy.structured_requirements if previous_policy else {}
    )
    previous_uses = previous_policy.allowed_uses if previous_policy else DEFAULT_ALLOWED_USES
    allowed_uses = updates.get("allowed_uses", previous_uses)
    requirements = {
        "training_codes": _training_codes(
            resource.required_training
            if "required_training" in updates
            else previous_requirements.get("training_codes", resource.required_training)
        ),
        "supervisor_required": updates.get(
            "supervision_required",
            previous_requirements.get(
                "supervisor_required", resource.supervision_required
            ),
        ),
        "supervised_windows": updates.get(
            "supervised_windows",
            previous_requirements.get(
                "supervised_windows", resource.supervised_windows
            ),
        ),
    }
    if requirements["supervisor_required"] and not requirements["supervised_windows"]:
        raise_api_error("validation_error", "supervised_windows are required when supervision_required is true.", 422)
    next_version = (
        session.scalar(
            select(func.max(ResourcePolicy.version)).where(
                ResourcePolicy.resource_id == resource.id
            )
        )
        or 0
    ) + 1
    policy = ResourcePolicy(
        id=str(uuid4()),
        resource_id=resource.id,
        version=next_version,
        structured_requirements=requirements,
        allowed_uses=allowed_uses,
        priority_policy=previous_policy.priority_policy if previous_policy else {},
        effective_at=datetime.now(timezone.utc),
        approved_by=user.id,
        activation_reason=policy_change_reason,
        is_demo=resource.is_demo,
    )
    session.add(policy)
    record_event(
        session,
        user,
        "resource",
        resource.id,
        "resource.updated",
        request.state.request_id,
        before=before,
        after={
            **{key: getattr(resource, key) for key in updates},
            "policy_version": next_version,
            "policy_change_reason": policy_change_reason,
        },
        is_demo=resource.is_demo,
    )
    session.flush()
    record_event(
        session,
        user,
        "resource_policy",
        policy.id,
        "resource_policy.activated",
        request.state.request_id,
        after={
            "resource_id": resource.id,
            "version": policy.version,
            "reason": policy.activation_reason,
        },
        is_demo=policy.is_demo,
    )
    _commit_or_conflict(session, "Resource could not be updated.")
    return _resource_response(session, user, resource, policy)


def _resource_read(
    resource: Resource,
    policy: ResourcePolicy | None,
    organization: Organization | None,
) -> ResourceRead:
    policy_requirements = policy.structured_requirements if policy else {}
    return ResourceRead(
        id=resource.id,
        owner_id=resource.owner_id,
        name=resource.name,
        category=resource.category,
        short_summary=resource.short_summary,
        description=resource.description,
        capability_tags=resource.capability_tags,
        location=resource.location,
        organization_id=resource.owner.organization_id,
        organization_name=(
            organization.name
            if organization
            else resource.owner.organization_id
        ),
        organization_type=organization.type if organization else "institution",
        city=resource.city,
        area=resource.area,
        id_required=resource.id_required,
        building=resource.building,
        room=resource.room,
        address_note=resource.address_note,
        status=resource.status,
        hold_reason=resource.hold_reason,
        hold_review_date=resource.hold_review_date,
        operating_hours=resource.weekly_operating_hours,
        weekly_operating_hours=resource.weekly_operating_hours,
        capacity=resource.capacity,
        quantity=resource.quantity,
        allowed_uses=policy.allowed_uses if policy else resource.allowed_uses,
        who_can_use=resource.who_can_use,
        required_training=_training_names(resource, policy),
        supervision_required=policy_requirements.get(
            "supervisor_required", resource.supervision_required
        ),
        supervised_windows=policy_requirements.get(
            "supervised_windows", resource.supervised_windows
        ),
        usage_rules=resource.usage_rules,
        safety_notes=resource.safety_notes,
        max_session_hours=resource.max_session_hours,
        advance_booking_window=resource.advance_booking_window,
        cancellation_cutoff=resource.cancellation_cutoff,
        accessories_included=resource.accessories_included,
        condition_notes=resource.condition_notes,
        access_model=resource.access_model,
        max_duration_minutes=resource.max_duration_minutes,
        exclusive_booking=resource.exclusive_booking,
        is_demo=resource.is_demo,
    )


def _resource_response(
    session: Session,
    user: User,
    resource: Resource,
    policy: ResourcePolicy | None = None,
) -> ResourceResponse:
    policy = policy or active_policy(session, resource.id)
    readiness = evaluate_readiness(session, user, resource)
    return ResourceResponse(
        resource=_resource_read(
            resource,
            policy,
            _organization_profile(session, resource),
        ),
        active_policy=ResourcePolicyRead.model_validate(policy) if policy else None,
        readiness=ReadinessRead.model_validate(readiness),
        eligibility_checklist=_eligibility_checklist(
            session, user, resource, policy, readiness, None, None, None
        ),
    )


def _organization_profile(
    session: Session,
    resource: Resource,
) -> Organization | None:
    return session.get(Organization, resource.owner.organization_id)


def _eligibility_checklist(
    session: Session,
    user: User,
    resource: Resource,
    policy: ResourcePolicy | None,
    readiness: dict,
    start_at: datetime | None,
    end_at: datetime | None,
    purpose: str | None,
) -> list[EligibilityChecklistItem]:
    blockers = {item["code"]: item for item in readiness["blockers"]}
    checklist = []

    def add(requirement: str, code: str, action: str) -> None:
        blocker = blockers.get(code)
        checklist.append(
            EligibilityChecklistItem(
                requirement=requirement,
                code=code,
                passed=blocker is None,
                message=blocker["message"] if blocker else f"{requirement} is satisfied.",
                next_action=blocker["next_action"] if blocker else action,
            )
        )

    if policy is None:
        add(
            "Approved access policy",
            "policy_missing",
            "A scoped manager must create and activate a policy version.",
        )
    add(
        "Resource is active",
        "maintenance_hold" if resource.status == "maintenance_hold" else "resource_retired",
        "Choose an active resource.",
    ) if resource.status != "active" else checklist.append(
        EligibilityChecklistItem(
            requirement="Resource is active",
            passed=True,
            message="Resource is active.",
            next_action="No action required.",
        )
    )

    requirements = policy.structured_requirements if policy else {}
    codes = requirements.get("training_codes", [])
    names = _training_names(resource, policy)
    for index, code in enumerate(codes):
        records = session.scalars(
            select(TrainingRecord).where(
                TrainingRecord.user_id == user.id,
                TrainingRecord.requirement_code == code,
                TrainingRecord.status == "valid",
                TrainingRecord.verified_by.is_not(None),
                TrainingRecord.valid_from <= datetime.now(timezone.utc),
            )
        ).all()
        valid = any(
            item.valid_to is None or _as_utc(item.valid_to) > datetime.now(timezone.utc)
            for item in records
        )
        checklist.append(
            EligibilityChecklistItem(
                requirement=names[index] if index < len(names) else code,
                code="missing_training" if not valid else None,
                passed=valid,
                message=(
                    "Verified training is current."
                    if valid
                    else "Required training is missing, expired, or not verified."
                ),
                next_action=(
                    "No action required."
                    if valid
                    else "Ask the authorized training owner to record a verified sign-off."
                ),
            )
        )
    supervised = requirements.get(
        "supervisor_required", resource.supervision_required
    )
    windows = requirements.get("supervised_windows", resource.supervised_windows)
    if supervised:
        is_covered = bool(windows)
        if start_at is not None and end_at is not None:
            is_covered = "supervisor_unavailable" not in blockers
        checklist.append(
            EligibilityChecklistItem(
                requirement="Supervision coverage",
                code="supervisor_unavailable" if not is_covered else None,
                passed=is_covered,
                message=(
                    "Supervised windows are configured."
                    if is_covered
                    else "No supervised windows are configured for this resource."
                ),
                next_action=(
                    "Select a covered slot."
                    if not is_covered
                    else "No action required."
                ),
            )
        )
    if purpose is not None and policy is not None:
        allowed = purpose in policy.allowed_uses
        checklist.append(
            EligibilityChecklistItem(
                requirement="Allowed use",
                code=None if allowed else "disallowed_purpose",
                passed=allowed,
                message=(
                    "Requested use is allowed."
                    if allowed
                    else "Requested use is not allowed by the active policy."
                ),
                next_action="Choose one of the resource's allowed uses.",
            )
        )
    if start_at is not None and end_at is not None:
        duration_hours = (end_at - start_at).total_seconds() / 3600
        within_duration_limit = (
            resource.max_session_hours is None
            or duration_hours <= resource.max_session_hours
        ) and (
            resource.max_duration_minutes is None
            or duration_hours * 60 <= resource.max_duration_minutes
        )
        checklist.append(
            EligibilityChecklistItem(
                requirement="Maximum session duration",
                code=None if within_duration_limit else "duration_exceeded",
                passed=within_duration_limit,
                message=(
                    "Requested duration is within the resource limit."
                    if within_duration_limit
                    else "Requested duration exceeds the resource limit."
                ),
                next_action=(
                    "No action required."
                    if within_duration_limit
                    else "Choose a shorter session."
                ),
            )
        )
        within_advance_window = (
            resource.advance_booking_window is None
            or _as_utc(start_at)
            <= datetime.now(timezone.utc)
            + timedelta(days=resource.advance_booking_window)
        )
        checklist.append(
            EligibilityChecklistItem(
                requirement="Advance booking window",
                code=None if within_advance_window else "advance_booking_window",
                passed=within_advance_window,
                message=(
                    "Requested time is within the advance booking window."
                    if within_advance_window
                    else "Requested time is outside the advance booking window."
                ),
                next_action=(
                    "No action required."
                    if within_advance_window
                    else "Choose a date within the allowed booking window."
                ),
            )
        )
        slot_blocker = next(
            (item for item in readiness["blockers"] if item["code"] == "slot_conflict"),
            None,
        )
        checklist.append(
            EligibilityChecklistItem(
                requirement="Requested time is available",
                code="slot_conflict" if slot_blocker else None,
                passed=slot_blocker is None,
                message=(
                    slot_blocker["message"]
                    if slot_blocker
                    else "The requested time is available."
                ),
                next_action=(
                    slot_blocker["next_action"]
                    if slot_blocker
                    else "No action required."
                ),
            )
        )
    return checklist


def _new_policy_from_resource(
    resource: Resource,
    allowed_uses: list[str],
    user: User,
    version: int,
    activation_reason: str,
) -> ResourcePolicy:
    return ResourcePolicy(
        id=str(uuid4()),
        resource_id=resource.id,
        version=version,
        structured_requirements={
            "training_codes": _training_codes(resource.required_training),
            "supervisor_required": resource.supervision_required,
            "supervised_windows": resource.supervised_windows,
        },
        allowed_uses=allowed_uses,
        priority_policy={},
        effective_at=datetime.now(timezone.utc),
        approved_by=user.id,
        activation_reason=activation_reason,
        is_demo=resource.is_demo,
    )


def _training_codes(names: list[str]) -> list[str]:
    result = []
    for name in names:
        code = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")
        result.append(code[:100])
    return result


def _training_names(resource: Resource, policy: ResourcePolicy | None) -> list[str]:
    if resource.required_training:
        return resource.required_training
    if policy is None:
        return []
    return list(policy.structured_requirements.get("training_codes", []))


def _location(building: str, room: str) -> str:
    return " · ".join(part for part in (building, room) if part)


def _next_availability(
    session: Session, resource: Resource, policy: ResourcePolicy | None
) -> datetime | None:
    if resource.status != "active" or not resource.weekly_operating_hours:
        return None
    now = datetime.now(timezone.utc)
    max_day = resource.advance_booking_window
    upper_day = min(30, max_day) if max_day is not None else 30
    bookings = session.scalars(
        select(Booking)
        .join(ResourceRequest)
        .where(
            ResourceRequest.resource_id == resource.id,
            Booking.status.in_(ACTIVE_BOOKING_STATES),
            Booking.end_at > now,
            Booking.start_at < now + timedelta(days=upper_day + 1),
        )
        .order_by(Booking.start_at)
    ).all()
    requirements = policy.structured_requirements if policy else {}
    supervisor_windows = requirements.get(
        "supervised_windows", resource.supervised_windows
    )
    supervisor_required = requirements.get(
        "supervisor_required", resource.supervision_required
    )
    duration = timedelta(hours=min(resource.max_session_hours or 1, 24))
    for offset in range(upper_day + 1):
        day = (now.astimezone(IST) + timedelta(days=offset)).date()
        weekday = day.isoweekday()
        for window in sorted(
            (row for row in resource.weekly_operating_hours if row["weekday"] == weekday),
            key=lambda row: row["start"],
        ):
            start_local = datetime.combine(day, time.fromisoformat(window["start"]), tzinfo=IST)
            end_local = datetime.combine(day, time.fromisoformat(window["end"]), tzinfo=IST)
            candidate = max(start_local.astimezone(timezone.utc), now)
            if candidate + duration > end_local.astimezone(timezone.utc):
                continue
            for booking in bookings:
                booking_start = _as_utc(booking.start_at)
                booking_end = _as_utc(booking.end_at)
                if candidate < booking_end and candidate + duration > booking_start:
                    candidate = booking_end
            candidate_local = candidate.astimezone(IST)
            session_end_local = (candidate + duration).astimezone(IST)
            supervisor_covered = not supervisor_required or any(
                row["weekday"] == candidate_local.isoweekday()
                and row["start"] <= candidate_local.strftime("%H:%M")
                and row["end"] >= session_end_local.strftime("%H:%M")
                for row in supervisor_windows
            )
            if (
                candidate + duration <= end_local.astimezone(timezone.utc)
                and supervisor_covered
                and not any(
                    candidate < _as_utc(booking.end_at)
                    and candidate + duration > _as_utc(booking.start_at)
                    for booking in bookings
                )
            ):
                return candidate
    return None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _commit_or_conflict(session: Session, message: str) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_api_error("conflict", message, 409)
