from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.dependencies import require_roles
from app.models import DiscoveryFeedback, User
from app.schemas import DiscoveryFeedbackCreate

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", status_code=201)
def submit_discovery_feedback(
    payload: DiscoveryFeedbackCreate,
    session: Session = Depends(get_session),
    user: User = Depends(
        require_roles("requester", "lab_manager", "institution_admin")
    ),
) -> dict:
    feedback = DiscoveryFeedback(
        id=str(uuid4()),
        user_id=user.id,
        is_helpful=payload.is_helpful,
        created_at=datetime.now(timezone.utc),
        is_demo=user.is_demo,
    )
    session.add(feedback)
    session.commit()
    return {"feedback": {"id": feedback.id, "created_at": feedback.created_at}}