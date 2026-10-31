import logging
from collections import deque
from threading import Lock
from time import monotonic
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_session
from app.dependencies import require_roles
from app.errors import raise_api_error
from app.models import User
from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from app.services.assistant_provider import (
    configured_assistant_provider,
    validate_model_intent,
)
from app.services.booking_assistant import determine_intent, run_rules, scoped_resources

router = APIRouter(prefix="/api/assistant", tags=["booking-assistant"])
logger = logging.getLogger(__name__)
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_WINDOW_SECONDS = 10 * 60


def _enforce_user_rate_limit(request: Request, user_id: str) -> None:
    now = monotonic()
    buckets: dict[str, deque[float]] = request.app.state.assistant_rate_limit_buckets
    lock: Lock = request.app.state.assistant_rate_limit_lock
    with lock:
        if now >= request.app.state.assistant_rate_limit_cleanup_at:
            expired = [
                account_id
                for account_id, entries in buckets.items()
                if not entries or entries[-1] <= now - RATE_LIMIT_WINDOW_SECONDS
            ]
            for account_id in expired:
                del buckets[account_id]
            request.app.state.assistant_rate_limit_cleanup_at = (
                now + RATE_LIMIT_WINDOW_SECONDS
            )
        timestamps = buckets.setdefault(user_id, deque())
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()
        if len(timestamps) >= RATE_LIMIT_REQUESTS:
            raise_api_error(
                "rate_limited",
                "Assistant message limit reached. Try again in ten minutes.",
                429,
            )
        timestamps.append(now)


@router.post("/chat", response_model=AssistantChatResponse)
def assistant_chat(
    payload: AssistantChatRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("requester", "lab_manager")),
) -> AssistantChatResponse:
    _enforce_user_rate_limit(request, user.id)
    try:
        request_id = str(UUID(str(request.state.request_id)))
    except ValueError:
        request_id = str(uuid4())
    started_at = monotonic()
    source: Literal["model", "rules"] = "rules"
    model_intent = None
    model_resource_ids = None
    model_reply = None

    intent_from_rules = determine_intent(payload.message)
    if (
        not intent_from_rules.startswith("unsupported_")
        and intent_from_rules not in {"explain_request", "general_help"}
    ):
        provider = configured_assistant_provider()
        if provider is not None:
            try:
                scoped = scoped_resources(session, user)
                safe_resources = [
                    {
                        "id": resource.id,
                        "name": resource.name,
                        "category": resource.category,
                        "status": resource.status,
                        "city": resource.city,
                        "area": resource.area,
                        "capability_tags": resource.capability_tags,
                    }
                    for resource in scoped
                ]
                model_output = validate_model_intent(
                    provider.interpret(payload.message, safe_resources)
                )
                model_intent = model_output.intent
                model_resource_ids = {
                    str(resource_id) for resource_id in model_output.resource_ids
                }
                model_reply = model_output.reply_text
                source = "model"
            except Exception:
                source = "rules"

    result = run_rules(
        session,
        user,
        payload.message,
        request_id,
        intent_override=model_intent,
        model_resource_ids=model_resource_ids,
        model_reply=model_reply,
        source=source,
    )
    latency_ms = round((monotonic() - started_at) * 1000)
    logger.info(
        "assistant_chat user_id=%s intent=%s source=%s latency_ms=%d request_id=%s",
        user.id,
        result.intent,
        source,
        latency_ms,
        request_id,
    )
    return result.response
