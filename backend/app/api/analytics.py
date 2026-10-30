from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_session
from app.dependencies import get_current_user
from app.domain.capacity_insights import build_resource_memory
from app.errors import raise_api_error
from app.models import Resource, User
from app.services.scope import ensure_same_organization

router = APIRouter(prefix="/api/resources", tags=["resource-memory"])


@router.get("/{resource_id}/memory")
def resource_memory(
    resource_id: str,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    resource = session.scalar(
        select(Resource)
        .options(joinedload(Resource.owner))
        .where(Resource.id == resource_id)
    )
    if resource is None:
        raise_api_error("not_found", "Resource not found.", 404)
    ensure_same_organization(user, resource)
    if (from_time is None) != (to_time is None):
        raise_api_error("validation_error", "from and to must be provided together.", 422)
    if from_time is not None:
        if from_time.tzinfo is None or to_time.tzinfo is None or to_time <= from_time:
            raise_api_error("validation_error", "The requested date range is invalid.", 422)
    try:
        return build_resource_memory(session, resource, from_time, to_time)
    except ValueError as error:
        raise_api_error("validation_error", str(error), 422)
