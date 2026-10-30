from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, Resource, ResourcePolicy, ResourceRequest, TrainingRecord, User


IST = ZoneInfo("Asia/Kolkata")
ACTIVE_BOOKING_STATES = (
    "CONFIRMED",
    "CHECKED_IN",
    "NO_SHOW",
    "RETURN_PENDING",
    "INCIDENT_REVIEW",
)

BLOCKERS = {
    "policy_missing": (
        "This resource is not ready for self-service because its access policy is missing or not approved.",
        "The resource owner or lab manager reviews and activates a policy version.",
    ),
    "maintenance_hold": (
        "This resource is on maintenance hold and cannot be booked.",
        "The resource owner or lab manager reviews the hold; it is not released automatically.",
    ),
    "missing_training": (
        "Required training is missing, expired, or not verified for this resource.",
        "Ask the authorized training owner to record a verified sign-off.",
    ),
    "supervisor_unavailable": (
        "A required supervisor is not available for this time slot.",
        "Choose a covered slot or ask the manager to arrange supervisor coverage.",
    ),
    "slot_conflict": (
        "This time slot is outside resource availability or conflicts with a confirmed booking.",
        "Choose an operating slot that does not overlap a confirmed booking.",
    ),
}
BLOCKER_ORDER = (
    "policy_missing",
    "maintenance_hold",
    "missing_training",
    "supervisor_unavailable",
    "slot_conflict",
)


def active_policy(session: Session, resource_id: str) -> ResourcePolicy | None:
    return session.scalar(
        select(ResourcePolicy)
        .where(
            ResourcePolicy.resource_id == resource_id,
            ResourcePolicy.effective_at.is_not(None),
            ResourcePolicy.approved_by.is_not(None),
        )
        .order_by(ResourcePolicy.version.desc())
        .limit(1)
    )


def evaluate_readiness(
    session: Session,
    user: User,
    resource: Resource,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    exclude_booking_id: str | None = None,
) -> dict:
    found: set[str] = set()
    missing_training_codes: list[str] = []
    policy = active_policy(session, resource.id)
    if policy is None:
        found.add("policy_missing")
    if resource.status == "maintenance_hold":
        found.add("maintenance_hold")

    requirements = policy.structured_requirements if policy else {}
    now = datetime.now(timezone.utc)
    for requirement_code in requirements.get("training_codes", []):
        records = session.scalars(
            select(TrainingRecord).where(
                TrainingRecord.user_id == user.id,
                TrainingRecord.requirement_code == requirement_code,
                TrainingRecord.status == "valid",
                TrainingRecord.verified_by.is_not(None),
                TrainingRecord.valid_from <= now,
            )
        ).all()
        if not any(
            record.valid_to is None or _as_utc(record.valid_to) > now
            for record in records
        ):
            found.add("missing_training")
            missing_training_codes.append(requirement_code)

    if start_at is not None and end_at is not None:
        local_start = _as_utc(start_at).astimezone(IST)
        local_end = _as_utc(end_at).astimezone(IST)
        if not _is_covered(
            resource.weekly_operating_hours, local_start, local_end
        ):
            found.add("slot_conflict")
        if requirements.get("supervisor_required") and not _is_covered(
            requirements.get("supervised_windows", []), local_start, local_end
        ):
            found.add("supervisor_unavailable")
        if resource.exclusive_booking:
            overlap_query = (
                select(Booking.id)
                .join(ResourceRequest, ResourceRequest.id == Booking.request_id)
                .where(
                    ResourceRequest.resource_id == resource.id,
                    Booking.status.in_(ACTIVE_BOOKING_STATES),
                    Booking.start_at < end_at,
                    Booking.end_at > start_at,
                )
            )
            if exclude_booking_id:
                overlap_query = overlap_query.where(Booking.id != exclude_booking_id)
            overlapping_id = session.scalar(overlap_query.limit(1))
            if overlapping_id is not None:
                found.add("slot_conflict")

    blockers = [
        {
            "code": code,
            "message": BLOCKERS[code][0],
            "next_action": BLOCKERS[code][1],
            **(
                {"requirement_codes": missing_training_codes}
                if code == "missing_training"
                else {}
            ),
        }
        for code in BLOCKER_ORDER
        if code in found
    ]
    return {"ready": not blockers, "blockers": blockers}


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _is_covered(windows: list[dict], start: datetime, end: datetime) -> bool:
    if start.date() != end.date():
        return False
    start_minute = start.hour * 60 + start.minute
    end_minute = end.hour * 60 + end.minute
    return any(
        window.get("weekday") == start.isoweekday()
        and _minute(window.get("start")) <= start_minute
        and _minute(window.get("end")) >= end_minute
        for window in windows
    )


def _minute(value: str | None) -> int:
    if value is None:
        return -1
    try:
        hour, minute = value.split(":", 1)
        return int(hour) * 60 + int(minute)
    except (ValueError, AttributeError):
        return -1
