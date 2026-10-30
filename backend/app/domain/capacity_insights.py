from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.readiness import active_policy
from app.models import (
    AllocationDecision,
    AuditEvent,
    Booking,
    HandoverReport,
    Incident,
    Resource,
    ResourceRequest,
    TrainingRecord,
)

IST = ZoneInfo("Asia/Kolkata")
BOOKING_STATES = {
    "CONFIRMED",
    "CHECKED_IN",
    "NO_SHOW",
    "RETURN_PENDING",
    "INCIDENT_REVIEW",
    "CLOSED",
}


def build_resource_memory(
    session: Session,
    resource: Resource,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    end = _utc(range_end or now)
    start = _utc(range_start or (end - timedelta(days=30)))
    if end <= start:
        raise ValueError("range_end must be later than range_start")

    operating = _operating_intervals(resource, start, end)
    requests = session.scalars(
        select(ResourceRequest).where(
            ResourceRequest.resource_id == resource.id,
            ResourceRequest.created_at >= start,
            ResourceRequest.created_at <= end,
        )
    ).all()
    bookings = session.scalars(
        select(Booking)
        .join(ResourceRequest)
        .where(
            ResourceRequest.resource_id == resource.id,
            Booking.start_at < end,
            Booking.end_at > start,
            Booking.status.in_(BOOKING_STATES),
        )
    ).all()
    booking_intervals = [
        _clip(_utc(row.start_at), _utc(row.end_at), start, end)
        for row in bookings
    ]
    booking_intervals = [item for item in booking_intervals if item]
    scheduled_hours = _hours(
        [
            _clip(_utc(row.start_at), _utc(row.end_at), start, end)
            for row in bookings
            if row.status == "CONFIRMED"
        ]
    )
    completed_hours = _completed_hours(session, bookings, start, end)
    blocked_intervals = _hold_intervals(session, resource, start, end)
    occupied_during_operating_hours = _merge_intervals(
        [
            overlap
            for occupied in booking_intervals + blocked_intervals
            for operating_interval in operating
            if (overlap := _clip(
                occupied[0],
                occupied[1],
                operating_interval[0],
                operating_interval[1],
            ))
        ]
    )
    blocked_by_reason = defaultdict(list)
    blocked_by_reason["maintenance_hold"].extend(blocked_intervals)
    for row in requests:
        if row.status != "INELIGIBLE":
            continue
        event = session.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "request",
                AuditEvent.entity_id == row.id,
                AuditEvent.action == "request.ineligible",
                AuditEvent.timestamp >= start,
                AuditEvent.timestamp <= end,
            )
            .order_by(AuditEvent.timestamp.desc())
            .limit(1)
        )
        if event is None:
            continue
        interval = _clip(_utc(row.start_at), _utc(row.end_at), start, end)
        if interval is None:
            continue
        for blocker in (event.after_summary or {}).get("blockers", []):
            code = blocker.get("code")
            if code in {"missing_training", "policy_missing", "supervisor_unavailable"}:
                blocked_by_reason[code].append(interval)

    waitlisted = session.scalars(
        select(AllocationDecision)
        .join(ResourceRequest)
        .where(
            ResourceRequest.resource_id == resource.id,
            AllocationDecision.outcome == "waitlisted",
            AllocationDecision.created_at >= start,
            AllocationDecision.created_at <= end,
        )
    ).all()
    waitlisted_requests = session.scalars(
        select(ResourceRequest).where(
            ResourceRequest.id.in_(
                sorted({row.request_id for row in waitlisted})
                or ["00000000-0000-0000-0000-000000000000"]
            )
        )
    ).all()
    all_request_ids = session.scalars(
        select(ResourceRequest.id).where(ResourceRequest.resource_id == resource.id)
    ).all()
    cancellation_events = session.scalars(
        select(AuditEvent).where(
            AuditEvent.entity_type == "request",
            AuditEvent.action == "request.cancelled",
            AuditEvent.timestamp >= start,
            AuditEvent.timestamp <= end,
            AuditEvent.entity_id.in_(all_request_ids or ["00000000-0000-0000-0000-000000000000"]),
        )
    ).all()
    no_show_count = len(session.scalars(
        select(AuditEvent.id).where(
            AuditEvent.entity_type == "booking",
            AuditEvent.action == "booking.no_show",
            AuditEvent.timestamp >= start,
            AuditEvent.timestamp <= end,
            AuditEvent.entity_id.in_([row.id for row in bookings] or ["00000000-0000-0000-0000-000000000000"]),
        )
    ).all())
    unresolved_incidents = session.scalars(
        select(Incident)
        .join(Booking, Incident.booking_id == Booking.id)
        .join(ResourceRequest, Booking.request_id == ResourceRequest.id)
        .where(
            ResourceRequest.resource_id == resource.id,
            Incident.created_at >= start,
            Incident.created_at <= end,
            Incident.status.not_in(("RESOLVED", "DISMISSED")),
        )
    ).all()
    maintenance_events = [
        event
        for event in session.scalars(
            select(AuditEvent).where(
                AuditEvent.entity_type == "resource",
                AuditEvent.entity_id == resource.id,
                AuditEvent.timestamp <= end,
            ).order_by(AuditEvent.timestamp)
        ).all()
        if event.action.startswith("resource.maintenance_hold")
        or "status" in (event.before_summary or {})
        or "status" in (event.after_summary or {})
    ]
    recs = _recommendations(
        session, resource, requests, maintenance_events, start, end
    )
    has_demo = resource.is_demo or any(row.is_demo for row in requests + bookings)
    return {
        "resource_id": resource.id,
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "metrics": {
            "available_hours": round(
                max(
                    0.0,
                    _hours(operating) - _hours(occupied_during_operating_hours),
                ),
                2,
            ),
            "scheduled_hours": round(scheduled_hours, 2),
            "completed_hours": round(completed_hours, 2),
            "cancellations": len(cancellation_events),
            "no_shows": no_show_count,
            "blocked_hours_by_reason": {
                code: round(_hours(_merge_intervals(intervals)), 2)
                for code, intervals in sorted(blocked_by_reason.items())
            },
            "waitlist_demand": {
                "requests": len(waitlisted),
                "hours": round(
                    sum(
                        (_utc(row.end_at) - _utc(row.start_at)).total_seconds() / 3600
                        for row in waitlisted_requests
                    ),
                    2,
                ),
            },
            "maintenance_holds": {
                "count": len(blocked_intervals),
                "hours": round(_hours(blocked_intervals), 2),
            },
            "unresolved_incidents": len(unresolved_incidents),
        },
        "recommendations": recs,
        "demo_data": has_demo,
        "label": "DEMO DATA — not live institutional statistics" if has_demo else None,
    }


def _recommendations(
    session: Session,
    resource: Resource,
    requests: list[ResourceRequest],
    hold_events: list[AuditEvent],
    start: datetime,
    end: datetime,
) -> list[dict]:
    result = []
    grouped_training: dict[str, list[ResourceRequest]] = defaultdict(list)
    supervised = []
    now = datetime.now(timezone.utc)
    for request in requests:
        event = session.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "request",
                AuditEvent.entity_id == request.id,
                AuditEvent.action == "request.ineligible",
                AuditEvent.timestamp >= start,
                AuditEvent.timestamp <= end,
            )
            .order_by(AuditEvent.timestamp.desc())
            .limit(1)
        )
        codes = [
            item.get("code")
            for item in (event.after_summary or {}).get("blockers", [])
        ] if event else []
        if codes == ["supervisor_unavailable"]:
            supervised.append(request)
        if "missing_training" in codes:
            requirement_codes = {
                code
                for blocker in (event.after_summary or {}).get("blockers", [])
                if blocker.get("code") == "missing_training"
                for code in blocker.get("requirement_codes", [])
            }
            if not requirement_codes:
                policy = active_policy(session, request.resource_id)
                requirement_codes = (
                    set(policy.structured_requirements.get("training_codes", []))
                    if policy
                    else set()
                )
            for requirement in requirement_codes:
                valid_record = session.scalar(
                    select(TrainingRecord.id).where(
                        TrainingRecord.user_id == request.requester_id,
                        TrainingRecord.requirement_code == requirement,
                        TrainingRecord.status == "valid",
                        TrainingRecord.verified_by.is_not(None),
                        TrainingRecord.valid_from <= now,
                        or_(
                            TrainingRecord.valid_to.is_(None),
                            TrainingRecord.valid_to > now,
                        ),
                    )
                )
                if valid_record is None:
                    grouped_training[requirement].append(request)
    for requirement, blocked_requests in grouped_training.items():
        users = {request.requester_id for request in blocked_requests}
        if len(users) < 2:
            continue
        policy = active_policy(session, resource.id)
        result.append(
            {
                "recommendation_code": "training_backlog",
                "text": (
                    f"Review the training backlog for {requirement}. {len(users)} users "
                    f"across {len(blocked_requests)} requests were blocked during "
                    f"{start.date()} to {end.date()}. The authorized training owner is "
                    f"{resource.owner.display_name}."
                ),
                "trigger_rule": "At least two distinct users blocked by one missing training code.",
                "required_evidence": {
                    "requirement_code": requirement,
                    "authorized_training_owner_id": resource.owner_id,
                },
                "source_record_references": {
                    "request_ids": sorted({request.id for request in blocked_requests}),
                    "policy_id": policy.id if policy else None,
                    "training_record_ids": _training_ids(session, users, requirement),
                },
                "source_counts": {
                    "distinct_users": len(users),
                    "requests": len(blocked_requests),
                },
                "range_start": start.isoformat(),
                "range_end": end.isoformat(),
                "limitations": ["Planning suggestion only; does not grant training or access."],
                "demo_data": any(request.is_demo for request in blocked_requests),
            }
        )
    if len(supervised) >= 2:
        windows = active_policy(session, resource.id)
        requested_window = ", ".join(
            f"{_utc(row.start_at).astimezone(IST).strftime('%a %H:%M')}-"
            f"{_utc(row.end_at).astimezone(IST).strftime('%H:%M')}"
            for row in supervised
        )
        result.append(
            {
                "recommendation_code": "supervised_slot_shortage",
                "text": (
                    f"Consider adding supervised coverage for {requested_window}. "
                    f"{len(supervised)} eligible requests in {start.date()} to {end.date()} "
                    "could not proceed because coverage was unavailable. This is a "
                    "planning suggestion, not an approval."
                ),
                "trigger_rule": "At least two requests blocked solely by supervised-window coverage.",
                "required_evidence": {
                    "requested_intervals": [
                        {"start_at": row.start_at.isoformat(), "end_at": row.end_at.isoformat()}
                        for row in supervised
                    ],
                    "policy_supervised_windows": (
                        windows.structured_requirements.get("supervised_windows", [])
                        if windows
                        else []
                    ),
                },
                "source_record_references": {
                    "request_ids": sorted({row.id for row in supervised}),
                    "policy_id": windows.id if windows else None,
                },
                "source_counts": {"requests": len(supervised)},
                "range_start": start.isoformat(),
                "range_end": end.isoformat(),
                "limitations": ["Coverage planning only; no request is approved automatically."],
                "demo_data": any(row.is_demo for row in supervised),
            }
        )
    if resource.status == "maintenance_hold" and resource.hold_review_date and resource.hold_review_date < date.today():
        result.append(
            {
                "recommendation_code": "maintenance_hold_review",
                "text": (
                    f"Review the maintenance hold for {resource.name}; its recorded review "
                    "date has passed. This does not release the resource automatically."
                ),
                "trigger_rule": "Resource status is maintenance_hold and hold_review_date is before today.",
                "required_evidence": {
                    "resource_id": resource.id,
                    "hold_review_date": resource.hold_review_date.isoformat(),
                    "hold_interval_events": [event.id for event in hold_events],
                },
                "source_record_references": {
                    "resource_id": resource.id,
                    "audit_event_ids": [event.id for event in hold_events],
                },
                "source_counts": {
                    "maintenance_holds": 1,
                    "blocked_hours": round(
                        _hours(_hold_intervals(session, resource, start, end)), 2
                    ),
                },
                "range_start": start.isoformat(),
                "range_end": end.isoformat(),
                "limitations": ["Review does not release the maintenance hold."],
                "demo_data": resource.is_demo,
            }
        )
    return result


def _training_ids(session: Session, user_ids: set[str], requirement: str) -> list[str]:
    return list(
        session.scalars(
            select(TrainingRecord.id).where(
                TrainingRecord.user_id.in_(user_ids),
                TrainingRecord.requirement_code == requirement,
            )
        ).all()
    ) if user_ids else []


def _hold_intervals(
    session: Session,
    resource: Resource,
    start: datetime,
    end: datetime,
) -> list[tuple[datetime, datetime]]:
    events = session.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.entity_type == "resource",
            AuditEvent.entity_id == resource.id,
            AuditEvent.timestamp <= end,
        )
        .order_by(AuditEvent.timestamp)
    ).all()
    held_at = None
    intervals = []
    for event in events:
        before = (event.before_summary or {}).get("status")
        after = (event.after_summary or {}).get("status")
        if before == "active" and after == "maintenance_hold":
            held_at = _utc(event.timestamp)
        elif before == "maintenance_hold" and after == "active" and held_at:
            clipped = _clip(held_at, _utc(event.timestamp), start, end)
            if clipped:
                intervals.append(clipped)
            held_at = None
    if held_at:
        clipped = _clip(held_at, end, start, end)
        if clipped:
            intervals.append(clipped)
    return _merge_intervals(intervals)


def _completed_hours(
    session: Session,
    bookings: list[Booking],
    start: datetime,
    end: datetime,
) -> float:
    completed = []
    for booking in bookings:
        if booking.status != "CLOSED":
            continue
        stages = set(
            session.scalars(
                select(HandoverReport.stage).where(
                    HandoverReport.booking_id == booking.id
                )
            ).all()
        )
        if {"IN", "OUT"} <= stages:
            interval = _clip(_utc(booking.start_at), _utc(booking.end_at), start, end)
            if interval:
                completed.append(interval)
    return _hours(completed)


def _operating_intervals(
    resource: Resource,
    start: datetime,
    end: datetime,
) -> list[tuple[datetime, datetime]]:
    local_start = start.astimezone(IST).date()
    local_end = end.astimezone(IST).date()
    current = local_start
    intervals = []
    while current <= local_end:
        for window in resource.weekly_operating_hours:
            if window.get("weekday") != current.isoweekday():
                continue
            local_begin = datetime.combine(current, time.fromisoformat(window["start"]), IST)
            local_finish = datetime.combine(current, time.fromisoformat(window["end"]), IST)
            clipped = _clip(local_begin.astimezone(timezone.utc), local_finish.astimezone(timezone.utc), start, end)
            if clipped:
                intervals.append(clipped)
        current += timedelta(days=1)
    return _merge_intervals(intervals)


def _clip(
    interval_start: datetime,
    interval_end: datetime,
    range_start: datetime,
    range_end: datetime,
) -> tuple[datetime, datetime] | None:
    clipped_start = max(interval_start, range_start)
    clipped_end = min(interval_end, range_end)
    return (clipped_start, clipped_end) if clipped_start < clipped_end else None


def _merge_intervals(
    intervals: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    ordered = sorted(intervals)
    merged = []
    for interval_start, interval_end in ordered:
        if not merged or interval_start > merged[-1][1]:
            merged.append((interval_start, interval_end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], interval_end))
    return merged


def _hours(intervals: list[tuple[datetime, datetime] | None]) -> float:
    return sum(
        (end - start).total_seconds() / 3600
        for interval in intervals
        if interval is not None
        for start, end in [interval]
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
