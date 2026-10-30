from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_session
from app.dependencies import get_current_user, require_roles
from app.errors import raise_api_error
from app.models import AccountProfile, OwnerApplication, User
from app.schemas import (
    AccountPatch,
    AccountRead,
    ChangePassword,
    OwnerApplicationCreate,
    OwnerApplicationRead,
    OwnerApplicationResponse,
)
from app.services.accounts import (
    account_payload,
    owner_application_payload,
    unique_display_name,
)
from app.services.auth import hash_password, verify_password
from app.services.audit_service import record_event

router = APIRouter(prefix="/api", tags=["accounts"])
NEW_PASSWORD_ROUNDS = 600_000


@router.get("/me", response_model=AccountRead)
def get_me(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AccountRead:
    profile = session.get(AccountProfile, user.id)
    return AccountRead.model_validate(account_payload(user, profile))


@router.patch("/me", response_model=AccountRead)
def update_me(
    payload: AccountPatch,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> AccountRead:
    profile = session.get(AccountProfile, user.id)
    if profile is None:
        profile = AccountProfile(
            user_id=user.id,
            email=None,
            full_name=user.display_name,
            email_verified=False,
            is_active=True,
            auth_version=0,
        )
        session.add(profile)

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(profile, field, value)
    if "full_name" in updates:
        user.display_name = unique_display_name(
            session, profile.full_name, user.organization_id, user.id
        )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_api_error("conflict", "The profile could not be updated.", 409)
    return AccountRead.model_validate(account_payload(user, profile))


@router.post("/me/change-password")
def change_password(
    payload: ChangePassword,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, bool]:
    if not verify_password(payload.current_password, user.password_hash):
        raise_api_error("invalid_credentials", "Current password is incorrect.", 401)

    profile = session.get(AccountProfile, user.id)
    if profile is None:
        profile = AccountProfile(
            user_id=user.id,
            email=None,
            full_name=user.display_name,
            email_verified=False,
            is_active=True,
            auth_version=0,
        )
        session.add(profile)
    user.password_hash = hash_password(payload.new_password, NEW_PASSWORD_ROUNDS)
    profile.auth_version += 1
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_api_error("conflict", "The password could not be changed.", 409)
    request.session["auth_version"] = profile.auth_version
    return {"ok": True}


@router.post(
    "/owner-applications",
    response_model=OwnerApplicationRead,
    status_code=201,
)
def apply_for_owner_access(
    payload: OwnerApplicationCreate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("requester")),
) -> OwnerApplicationRead:
    pending = session.scalar(
        select(OwnerApplication.id).where(
            OwnerApplication.applicant_id == user.id,
            OwnerApplication.status == "pending",
        )
    )
    if pending is not None:
        raise_api_error(
            "conflict", "You already have an owner application under review.", 409
        )
    if session.get(AccountProfile, user.id) is None:
        session.add(
            AccountProfile(
                user_id=user.id,
                email=None,
                full_name=user.display_name,
                email_verified=False,
                is_active=True,
                auth_version=0,
            )
        )
    application = OwnerApplication(
        id=str(uuid4()),
        applicant_id=user.id,
        organization=payload.organization,
        role_in_organization=payload.role_in_organization,
        reason=payload.reason,
        resources_to_list=payload.resources_to_list,
        status="pending",
        decision_reason=None,
        decided_by=None,
        created_at=datetime.now(timezone.utc),
        decided_at=None,
        is_demo=user.is_demo,
    )
    session.add(application)
    record_event(
        session,
        user,
        "owner_application",
        application.id,
        "owner_application.submitted",
        request.state.request_id,
        after={
            "organization": application.organization,
            "status": application.status,
        },
        is_demo=user.is_demo,
    )
    _commit(session, "The owner application could not be submitted.")
    return OwnerApplicationRead.model_validate(
        owner_application_payload(session, application)
    )


@router.get("/me/owner-application", response_model=OwnerApplicationResponse)
def my_owner_application(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> OwnerApplicationResponse:
    application = session.scalar(
        select(OwnerApplication)
        .where(OwnerApplication.applicant_id == user.id)
        .order_by(OwnerApplication.created_at.desc())
        .limit(1)
    )
    record_event(
        session,
        user,
        "owner_application" if application else "owner_application_query",
        application.id if application else user.id,
        "owner_application.viewed",
        request.state.request_id,
        after={"application_id": application.id if application else None},
        is_demo=user.is_demo,
    )
    session.commit()
    return OwnerApplicationResponse(
        application=(
            owner_application_payload(session, application)
            if application is not None
            else None
        )
    )


def _commit(session: Session, message: str) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_api_error("conflict", message, 409)
