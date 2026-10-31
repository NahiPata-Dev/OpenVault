from collections import deque
from time import monotonic

from fastapi import APIRouter, Depends, Request
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.errors import raise_api_error
from app.models import Organization, Resource, User
from app.schemas import PublicSummaryResponse

router = APIRouter(prefix="/api/public", tags=["public"])
RATE_LIMIT_REQUESTS = 60
RATE_LIMIT_WINDOW_SECONDS = 60


def _enforce_summary_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = monotonic()
    buckets: dict[str, deque[float]] = request.app.state.public_summary_buckets
    lock = request.app.state.public_summary_lock
    with lock:
        cleanup_at = request.app.state.public_summary_cleanup_at
        if now >= cleanup_at:
            cutoff = now - RATE_LIMIT_WINDOW_SECONDS
            expired = [
                address
                for address, timestamps in buckets.items()
                if not timestamps or timestamps[-1] <= cutoff
            ]
            for address in expired:
                del buckets[address]
            request.app.state.public_summary_cleanup_at = (
                now + RATE_LIMIT_WINDOW_SECONDS
            )

        requests = buckets.setdefault(client_ip, deque())
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        while requests and requests[0] <= cutoff:
            requests.popleft()
        if len(requests) >= RATE_LIMIT_REQUESTS:
            raise_api_error(
                "rate_limited",
                "Too many public summary requests. Try again in one minute.",
                429,
            )
        requests.append(now)


@router.get("/summary", response_model=PublicSummaryResponse)
def public_summary(
    request: Request,
    session: Session = Depends(get_session),
) -> PublicSummaryResponse:
    _enforce_summary_rate_limit(request)
    city_rows = session.execute(
        select(
            Organization.city,
            func.count(Resource.id),
            func.count(distinct(Organization.id)),
        )
        .outerjoin(User, User.organization_id == Organization.id)
        .outerjoin(
            Resource,
            and_(
                Resource.owner_id == User.id,
                Resource.is_demo.is_(True),
            ),
        )
        .where(Organization.is_demo.is_(True))
        .group_by(Organization.city)
        .order_by(Organization.city)
    ).all()
    categories = session.scalars(
        select(Resource.category)
        .where(Resource.is_demo.is_(True))
        .distinct()
        .order_by(Resource.category)
    ).all()
    return PublicSummaryResponse(
        cities=[
            {
                "city": city,
                "resource_count": resource_count,
                "organization_count": organization_count,
            }
            for city, resource_count, organization_count in city_rows
        ],
        categories=categories,
    )
