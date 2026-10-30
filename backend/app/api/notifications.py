from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_session
from app.dependencies import get_current_user
from app.errors import raise_api_error
from app.models import Notification, User
from app.services.notification_service import refresh_time_notifications

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = Query(default=False),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    items = refresh_time_notifications(session, user)
    if unread_only:
        items = [item for item in items if item["read_at"] is None]
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_api_error("conflict", "Notifications could not be refreshed.", 409)
    return {"items": items, "total": len(items)}


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    notification = session.get(Notification, notification_id)
    if notification is None:
        raise_api_error("not_found", "Notification not found.", 404)
    if notification.recipient_id != user.id:
        raise_api_error("forbidden", "You can mark only your own notifications as read.", 403)
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        session.commit()
    return {
        "notification": {
            "id": notification.id,
            "type": notification.type,
            "related_entity_type": notification.related_entity_type,
            "related_entity_id": notification.related_entity_id,
            "read_at": notification.read_at.isoformat(),
            "created_at": notification.created_at.isoformat(),
        }
    }
