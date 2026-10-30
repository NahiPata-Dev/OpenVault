from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_session
from app.dependencies import require_roles
from app.errors import raise_api_error
from app.models import Resource, ResourcePolicy, User
from app.schemas import PolicyActivate, PolicyDraftCreate, ResourcePolicyRead
from app.services.audit_service import record_event
from app.services.scope import ensure_resource_write_scope

router = APIRouter(prefix="/api/resources", tags=["policies"])


@router.post("/{resource_id}/policy-drafts", status_code=201)
def create_policy_draft(
    resource_id: str,
    payload: PolicyDraftCreate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("lab_manager", "institution_admin")),
) -> dict:
    resource = session.get(Resource, resource_id)
    if resource is None:
        raise_api_error("not_found", "Resource not found.", 404)
    ensure_resource_write_scope(user, resource)
    version = session.scalar(
        select(func.max(ResourcePolicy.version)).where(
            ResourcePolicy.resource_id == resource.id
        )
    ) or 0
    policy = ResourcePolicy(
        id=str(uuid4()),
        resource_id=resource.id,
        version=version + 1,
        structured_requirements=payload.structured_requirements,
        allowed_uses=payload.allowed_uses,
        priority_policy=payload.priority_policy,
        effective_at=None,
        approved_by=None,
        activation_reason=None,
        is_demo=resource.is_demo,
    )
    session.add(policy)
    session.flush()
    record_event(
        session,
        user,
        "resource_policy",
        policy.id,
        "resource_policy.drafted",
        request.state.request_id,
        after={"resource_id": resource.id, "version": policy.version},
        is_demo=policy.is_demo,
    )
    _commit(session, "The policy draft could not be saved.")
    return {"policy": ResourcePolicyRead.model_validate(policy).model_dump(mode="json")}


@router.post("/{resource_id}/policies/{version}/activate")
def activate_policy(
    resource_id: str,
    version: int,
    payload: PolicyActivate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("lab_manager")),
) -> dict:
    resource = session.get(Resource, resource_id)
    if resource is None:
        raise_api_error("not_found", "Resource not found.", 404)
    ensure_resource_write_scope(user, resource)
    policy = session.scalar(
        select(ResourcePolicy).where(
            ResourcePolicy.resource_id == resource.id,
            ResourcePolicy.version == version,
        )
    )
    if policy is None:
        raise_api_error("not_found", "Policy version not found.", 404)
    if policy.effective_at is not None:
        if policy.activation_reason == payload.reason:
            return {
                "policy": ResourcePolicyRead.model_validate(policy).model_dump(mode="json"),
                "audit_event_id": None,
            }
        raise_api_error("conflict", "This policy version is already active.", 409)

    policy.effective_at = datetime.now(timezone.utc)
    policy.approved_by = user.id
    policy.activation_reason = payload.reason
    event = record_event(
        session,
        user,
        "resource_policy",
        policy.id,
        "resource_policy.activated",
        request.state.request_id,
        after={
            "resource_id": resource.id,
            "version": policy.version,
            "reason": payload.reason,
        },
        is_demo=policy.is_demo,
    )
    _commit(session, "The policy could not be activated.")
    return {
        "policy": ResourcePolicyRead.model_validate(policy).model_dump(mode="json"),
        "audit_event_id": event.id,
    }


def _commit(session: Session, message: str) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_api_error("conflict", message, 409)
