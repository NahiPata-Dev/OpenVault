from datetime import datetime, timedelta, timezone
from typing import Any


USAGE_WINDOW = timedelta(days=30)
MAX_BOOKED_HOURS = 10
ALGORITHM_VERSION = "northstar-allocation-v1"


def rank_eligible_requests(
    candidates: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return policy inputs and a human-review recommendation, never an approval."""
    now = _as_utc(now or datetime.now(timezone.utc))
    window_start = now - USAGE_WINDOW
    evaluated = []
    for candidate in candidates:
        completed_count = int(candidate.get("completed_bookings_30d", 0))
        booked_hours = float(candidate.get("booked_hours_30d", 0))
        evaluated.append(
            {
                **candidate,
                "created_at": _as_utc(candidate.get("created_at")).isoformat(),
                "completed_bookings_30d": completed_count,
                "booked_hours_30d": booked_hours,
                "newcomer": completed_count == 0,
                "within_usage_limit": booked_hours < MAX_BOOKED_HOURS,
            }
        )

    eligible = [row for row in evaluated if row["within_usage_limit"]]
    eligible.sort(
        key=lambda row: (
            not row["newcomer"],
            row["booked_hours_30d"],
            row["created_at"],
            row["request_id"],
        )
    )
    first_rank = _rank_key(eligible[0]) if eligible else None
    tie_group = sorted(
        row["request_id"] for row in eligible if _rank_key(row) == first_rank
    )
    recommendation = (
        "manager_choice_required"
        if len(tie_group) > 1
        else "review_top_ranked_request"
        if eligible
        else "no_request_within_usage_limit"
    )
    inputs_snapshot = {
        "algorithm_version": ALGORITHM_VERSION,
        "window_start": window_start.isoformat(),
        "window_end": now.isoformat(),
        "usage_limit_hours": MAX_BOOKED_HOURS,
        "candidates": [
            {
                "request_id": row["request_id"],
                "requester_id": row.get("requester_id"),
                "created_at": row["created_at"],
                "newcomer": row["newcomer"],
                "completed_bookings_30d": row["completed_bookings_30d"],
                "booked_hours_30d": row["booked_hours_30d"],
                "within_usage_limit": row["within_usage_limit"],
            }
            for row in sorted(evaluated, key=lambda row: row["request_id"])
        ],
        "ranked_request_ids": [row["request_id"] for row in eligible],
        "excluded_over_limit_request_ids": sorted(
            row["request_id"] for row in evaluated if not row["within_usage_limit"]
        ),
        "tie_group": tie_group,
        "recommendation": recommendation,
    }
    return {
        **inputs_snapshot,
        "inputs_snapshot": inputs_snapshot,
    }


def _as_utc(value: datetime | str | None) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _rank_key(row: dict[str, Any]) -> tuple:
    return (
        not row["newcomer"],
        row["booked_hours_30d"],
        row["created_at"],
    )
