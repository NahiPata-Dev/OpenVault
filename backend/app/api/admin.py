from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_session
from app.dependencies import require_roles
from app.errors import raise_api_error
from app.models import (
    AccountProfile,
    Booking,
    Incident,
    OwnerApplication,
    Resource,
    ResourceRequest,
    User,
)
from app.schemas import (
    AdminUserRead,
    DemoResetRequest,
    OwnerApplicationDecision,
    OwnerApplicationRead,
)
from app.services.accounts import (
    organization_scope,
    owner_application_payload,
    unique_display_name,
)
from app.services.audit_service import record_event
from app.seed import seed_database

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserRead])
def list_users(
    session: Session = Depends(get_session),
    _user: User = Depends(require_roles("institution_admin")),
) -> list[AdminUserRead]:
    users = session.scalars(select(User).order_by(User.display_name)).all()
    profiles = {
        profile.user_id: profile
        for profile in session.scalars(select(AccountProfile)).all()
    }
    return [
        AdminUserRead(
            id=user.id,
            full_name=profiles[user.id].full_name
            if user.id in profiles
            else user.display_name,
            email=profiles[user.id].email if user.id in profiles else None,
            organization_name=(
                profiles[user.id].organization_name if user.id in profiles else None
            ),
            role=user.role,
            status=(
                "active"
                if user.id not in profiles or profiles[user.id].is_active
                else "inactive"
            ),
            is_demo=user.is_demo,
        )
        for user in users
    ]


@router.get(
    "/owner-applications", response_model=list[OwnerApplicationRead]
)
def list_owner_applications(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("institution_admin")),
) -> list[OwnerApplicationRead]:
    applications = session.scalars(
        select(OwnerApplication).order_by(
            OwnerApplication.created_at.desc(), OwnerApplication.id
        )
    ).all()
    record_event(
        session,
        user,
        "owner_application_query",
        user.id,
        "owner_applications.listed",
        request.state.request_id,
        after={"result_count": len(applications)},
        is_demo=user.is_demo,
    )
    session.commit()
    return [
        OwnerApplicationRead.model_validate(
            owner_application_payload(session, application)
        )
        for application in applications
    ]


@router.post(
    "/owner-applications/{application_id}/decision",
    response_model=OwnerApplicationRead,
)
def decide_owner_application(
    application_id: UUID,
    payload: OwnerApplicationDecision,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("institution_admin")),
) -> OwnerApplicationRead:
    application = session.get(OwnerApplication, str(application_id))
    if application is None:
        raise_api_error("not_found", "Owner application not found.", 404)
    if application.status != "pending":
        raise_api_error("invalid_state", "This owner application was already decided.", 409)

    applicant = session.get(User, application.applicant_id)
    profile = session.get(AccountProfile, application.applicant_id)
    if applicant is None or profile is None:
        raise_api_error("invalid_state", "The applicant account is unavailable.", 409)

    now = datetime.now(timezone.utc)
    old_status = application.status
    application.status = payload.outcome
    application.decision_reason = payload.reason
    application.decided_by = user.id
    application.decided_at = now
    before = {
        "status": old_status,
        "role": applicant.role,
        "organization_id": applicant.organization_id,
    }
    after = {"status": application.status, "reason": application.decision_reason}
    if payload.outcome == "approved":
        applicant.role = "lab_manager"
        applicant.organization_id = organization_scope(application.organization, applicant.id)
        applicant.display_name = unique_display_name(
            session,
            profile.full_name,
            applicant.organization_id,
            applicant.id,
        )
        profile.organization_name = application.organization
        after.update(
            {
                "role": applicant.role,
                "organization_id": applicant.organization_id,
            }
        )
    record_event(
        session,
        user,
        "owner_application",
        application.id,
        f"owner_application.{payload.outcome}",
        request.state.request_id,
        before=before,
        after=after,
        is_demo=application.is_demo,
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_api_error("conflict", "The owner application decision could not be saved.", 409)
    return OwnerApplicationRead.model_validate(
        owner_application_payload(session, application)
    )


@router.post("/demo-reset")
def reset_demo(
    payload: DemoResetRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("institution_admin")),
) -> dict:
    if not request.app.state.demo_mode:
        raise_api_error(
            "forbidden",
            "Demo reset is disabled outside the restricted demo environment.",
            403,
        )
    if payload.confirmation != "RESET_DEMO_DATA":
        raise_api_error("validation_error", "Reset confirmation does not match.", 422)
    if user.organization_id != "northstar-engineering-lab-demo":
        raise_api_error("forbidden", "Demo reset is limited to Northstar DEMO.", 403)
    counts = {
        "resources": _demo_count(session, Resource),
        "requests": _demo_count(session, ResourceRequest),
        "bookings": _demo_count(session, Booking),
        "incidents": _demo_count(session, Incident),
    }
    seed_database(
        request.app.state.session_factory,
        request.app.state.demo_password,
        force=True,
    )
    return {"ok": True, "reset_counts": counts}


def _demo_count(session: Session, model) -> int:
    return session.scalar(
        select(func.count()).select_from(model).where(model.is_demo.is_(True))
    ) or 0
