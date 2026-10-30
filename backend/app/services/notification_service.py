from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.state_transitions import apply_transition
from app.models import Booking, HandoverReport, Notification, ResourceRequest, User


def create_notification(
    session: Session,
    recipient_id: str,
    notification_type: str,
    entity_type: str,
    entity_id: str,
    is_demo: bool,
) -> Notification:
    existing = session.scalar(
        select(Notification).where(
            Notification.recipient_id == recipient_id,
            Notification.type == notification_type,
            Notification.related_entity_type == entity_type,
            Notification.related_entity_id == entity_id,
        )
    )
    if existing is not None:
        return existing
    notification = Notification(
        id=str(uuid5(NAMESPACE_URL, f"openvault:{recipient_id}:{notification_type}:{entity_id}")),
        recipient_id=recipient_id,
        type=notification_type,
        related_entity_type=entity_type,
        related_entity_id=entity_id,
        read_at=None,
        created_at=datetime.now(timezone.utc),
        is_demo=is_demo,
    )
    session.add(notification)
    return notification


def refresh_time_notifications(session: Session, user: User) -> list[dict]:
    now = datetime.now(timezone.utc)
    bookings = session.scalars(
        select(Booking)
        .join(ResourceRequest)
        .options(
            joinedload(Booking.request),
            joinedload(Booking.contracts),
            joinedload(Booking.handover_reports),
        )
        .where(ResourceRequest.requester_id == user.id)
    ).unique().all()
    derived_overdue = []
    for booking in bookings:
        start, end = _as_utc(booking.start_at), _as_utc(booking.end_at)
        has_in = any(report.stage == "IN" for report in booking.handover_reports)
        has_out = any(report.stage == "OUT" for report in booking.handover_reports)
        if booking.status == "CONFIRMED" and now >= start + timedelta(minutes=30) and not has_in:
            apply_transition(
                session,
                booking,
                "booking",
                "NO_SHOW",
                None,
                action="booking.no_show",
            )
        if booking.status == "NO_SHOW" and now >= end and not has_in:
            for contract in booking.contracts:
                contract.status = "CANCELLED"
        if start - timedelta(minutes=15) <= now < end and not has_in and booking.status == "CONFIRMED":
            create_notification(
                session,
                user.id,
                "checkin_due",
                "booking",
                booking.id,
                booking.is_demo,
            )
        if has_in and not has_out and now >= end and booking.status in {"CHECKED_IN", "RETURN_PENDING"}:
            derived_overdue.append(
                {
                    "id": str(uuid5(NAMESPACE_URL, f"openvault:overdue:{booking.id}")),
                    "type": "overdue_return",
                    "related_entity_type": "booking",
                    "related_entity_id": booking.id,
                    "read_at": None,
                    "created_at": end.isoformat(),
                    "is_demo": booking.is_demo,
                }
            )
    session.flush()
    rows = session.scalars(
        select(Notification)
        .where(Notification.recipient_id == user.id)
        .order_by(Notification.created_at.desc())
    ).all()
    items = [
        {
            "id": row.id,
            "type": row.type,
            "related_entity_type": row.related_entity_type,
            "related_entity_id": row.related_entity_id,
            "read_at": _as_utc(row.read_at).isoformat() if row.read_at else None,
            "created_at": _as_utc(row.created_at).isoformat(),
            "is_demo": row.is_demo,
        }
        for row in rows
    ]
    existing_ids = {item["id"] for item in items}
    items.extend(item for item in derived_overdue if item["id"] not in existing_ids)
    return items


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
