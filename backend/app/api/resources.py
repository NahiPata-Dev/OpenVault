from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_session
from app.dependencies import get_current_user, require_roles
from app.domain.readiness import active_policy, evaluate_readiness
from app.errors import raise_api_error
from app.models import Resource, User
from app.schemas import (
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


@router.get("", response_model=ResourceListResponse)
def list_resources(
    query: str | None = Query(default=None, max_length=160),
    category: str | None = Query(default=None, max_length=80),
    available_from: datetime | None = None,
    available_to: datetime | None = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ResourceListResponse:
    if (available_from is None) != (available_to is None):
        raise_api_error(
            "validation_error",
            "available_from and available_to must be provided together.",
            422,
        )
    if available_from is not None and available_to <= available_from:
        raise_api_error("validation_error", "The requested interval is invalid.", 422)

    resources = session.scalars(
        select(Resource)
        .options(joinedload(Resource.owner))
        .where(Resource.owner.has(organization_id=user.organization_id))
        .order_by(Resource.name)
    ).unique().all()
    needle = query.casefold().strip() if query else None
    results: list[ResourceListItem] = []
    for resource in resources:
        if category and resource.category.casefold() != category.casefold():
            continue
        if needle:
            fields = [
                resource.name,
                resource.category,
                resource.location,
                *resource.capability_tags,
            ]
            if not any(needle in field.casefold() for field in fields):
                continue
        results.append(
            ResourceListItem(
                id=resource.id,
                name=resource.name,
                category=resource.category,
                capability_tags=resource.capability_tags,
                location=resource.location,
                status=resource.status,
                weekly_operating_hours=resource.weekly_operating_hours,
                readiness=ReadinessRead.model_validate(
                    evaluate_readiness(
                        session, user, resource, available_from, available_to
                    )
                ),
            )
        )
    return ResourceListResponse(items=results, total=len(results))


@router.get("/{resource_id}", response_model=ResourceResponse)
def get_resource(
    resource_id: str,
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
    ensure_same_organization(user, resource)
    return _resource_response(session, user, resource)


@router.post("", response_model=ResourceResponse, status_code=201)
def create_resource(
    payload: ResourceCreate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("lab_manager", "institution_admin")),
) -> ResourceResponse:
    resource = Resource(
        id=str(uuid4()),
        owner_id=user.id,
        name=payload.name.strip(),
        category=payload.category.strip(),
        capability_tags=payload.capability_tags,
        location=payload.location.strip(),
        status=payload.status,
        hold_review_date=payload.hold_review_date,
        weekly_operating_hours=[
            item.model_dump() for item in payload.weekly_operating_hours
        ],
        max_duration_minutes=payload.max_duration_minutes,
        exclusive_booking=payload.exclusive_booking,
        is_demo=True,
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
    )
    _commit_or_conflict(session, "Resource could not be created.")
    return _resource_response(session, user, resource)


@router.patch("/{resource_id}", response_model=ResourceResponse)
def update_resource(
    resource_id: str,
    payload: ResourcePatch,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("lab_manager", "institution_admin")),
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
    if "status" in updates:
        resulting_date = updates.get("hold_review_date", resource.hold_review_date)
        if updates["status"] == "maintenance_hold" and resulting_date is None:
            raise_api_error(
                "validation_error",
                "hold_review_date is required for a maintenance hold.",
                422,
            )
        if updates["status"] == "active" and "hold_review_date" not in updates:
            updates["hold_review_date"] = None
    elif updates.get("hold_review_date") is None and "hold_review_date" in updates:
        if resource.status == "maintenance_hold":
            raise_api_error(
                "validation_error",
                "A maintenance hold must have a review date.",
                422,
            )

    before = {key: getattr(resource, key) for key in updates}
    for key, value in updates.items():
        if key == "weekly_operating_hours" and value is not None:
            value = [item.model_dump() for item in payload.weekly_operating_hours]
        if value is not None or key == "hold_review_date":
            setattr(resource, key, value)
    after = {key: getattr(resource, key) for key in updates}
    record_event(
        session,
        user,
        "resource",
        resource.id,
        "resource.updated",
        request.state.request_id,
        before=before,
        after=after,
    )
    _commit_or_conflict(session, "Resource could not be updated.")
    return _resource_response(session, user, resource)


def _resource_response(session: Session, user: User, resource: Resource) -> ResourceResponse:
    policy = active_policy(session, resource.id)
    return ResourceResponse(
        resource=ResourceRead.model_validate(resource),
        active_policy=ResourcePolicyRead.model_validate(policy) if policy else None,
        readiness=ReadinessRead.model_validate(evaluate_readiness(session, user, resource)),
    )


def _commit_or_conflict(session: Session, message: str) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_api_error("conflict", message, 409)
