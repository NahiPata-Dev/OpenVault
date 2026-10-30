from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.domain.readiness import active_policy, evaluate_readiness
from app.errors import raise_api_error
from app.models import Resource, User


def evaluate_eligibility(
    session: Session,
    user: User,
    resource: Resource,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    purpose: str | None = None,
    exclude_booking_id: str | None = None,
) -> dict:
    if start_at is not None and end_at is not None and end_at <= start_at:
        raise_api_error("validation_error", "The requested interval is invalid.", 422)

    policy = active_policy(session, resource.id)
    if (
        purpose is not None
        and policy is not None
        and purpose not in policy.allowed_uses
    ):
        raise_api_error(
            "validation_error",
            "The requested purpose is not permitted by the active resource policy.",
            422,
        )
    if (
        start_at is not None
        and end_at is not None
        and (
            resource.max_session_hours is not None
            and (end_at - start_at).total_seconds()
            > resource.max_session_hours * 3600
            or resource.max_duration_minutes is not None
            and (end_at - start_at).total_seconds()
            > resource.max_duration_minutes * 60
        )
    ):
        raise_api_error(
            "validation_error",
            "The requested interval exceeds the resource maximum duration.",
            422,
        )
    if start_at is not None and resource.advance_booking_window is not None:
        if start_at > datetime.now(start_at.tzinfo) + timedelta(days=resource.advance_booking_window):
            raise_api_error(
                "validation_error",
                "The requested start is outside the resource advance-booking window.",
                422,
            )
    return evaluate_readiness(
        session, user, resource, start_at, end_at, exclude_booking_id
    )


def require_eligible(result: dict) -> None:
    if result["blockers"]:
        raise_api_error(
            "ineligible",
            "This resource cannot be booked for the selected request.",
            422,
            details=[
                {
                    "code": blocker["code"],
                    "message": blocker["message"],
                    **(
                        {"requirement_codes": blocker["requirement_codes"]}
                        if blocker.get("requirement_codes")
                        else {}
                    ),
                }
                for blocker in result["blockers"]
            ],
        )
