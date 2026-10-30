from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.dependencies import require_roles
from app.errors import raise_api_error
from app.models import Booking, Incident, Resource, ResourceRequest, User
from app.schemas import DemoResetRequest
from app.seed import reset_demo_data, seed_database

router = APIRouter(prefix="/api/admin", tags=["admin"])


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
    reset_demo_data(session)
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
