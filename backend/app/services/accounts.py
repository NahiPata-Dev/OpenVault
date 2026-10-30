import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountProfile, OwnerApplication, User


def organization_scope(organization_name: str | None, user_id: str) -> str:
    if organization_name:
        normalized = " ".join(organization_name.casefold().split())
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"org-{digest}"
    return f"account-{user_id}"


def unique_display_name(
    session: Session, full_name: str, organization_id: str, user_id: str
) -> str:
    conflict = session.scalar(
        select(User.id).where(
            User.organization_id == organization_id,
            User.display_name == full_name,
            User.id != user_id,
        )
    )
    if conflict is None:
        return full_name
    suffix = user_id[:8]
    return f"{full_name[: 119 - len(suffix)]} ({suffix})"


def account_payload(user: User, profile: AccountProfile | None) -> dict:
    return {
        "id": user.id,
        "full_name": profile.full_name if profile else user.display_name,
        "email": profile.email if profile else None,
        "organization_name": profile.organization_name if profile else None,
        "phone": profile.phone if profile else None,
        "intended_use": profile.intended_use if profile else None,
        "role": user.role,
        "status": "active" if profile is None or profile.is_active else "inactive",
    }


def owner_application_payload(
    session: Session, application: OwnerApplication
) -> dict:
    applicant = session.get(User, application.applicant_id)
    profile = (
        session.get(AccountProfile, application.applicant_id)
        if applicant is not None
        else None
    )
    return {
        "id": application.id,
        "applicant_id": application.applicant_id,
        "applicant_name": profile.full_name if profile else (
            applicant.display_name if applicant else "Unknown applicant"
        ),
        "applicant_email": profile.email if profile else None,
        "organization": application.organization,
        "role_in_organization": application.role_in_organization,
        "reason": application.reason,
        "resources_to_list": application.resources_to_list,
        "status": application.status,
        "decision_reason": application.decision_reason,
        "decided_by": application.decided_by,
        "created_at": application.created_at,
        "decided_at": application.decided_at,
    }
