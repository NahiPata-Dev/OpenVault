from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from app.schemas import ResourceMatchResult


class ResourceMatchProvider(Protocol):
    def match(self, goal: str, candidates: list[dict]) -> dict: ...


def validate_provider_result(
    payload: dict,
    allowed_resource_ids: set[str],
    deterministic_fallback: ResourceMatchResult,
) -> ResourceMatchResult:
    try:
        result = ResourceMatchResult.model_validate(payload)
        candidate_ids = [str(candidate.resource_id) for candidate in result.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Duplicate candidate IDs")
        if any(resource_id not in allowed_resource_ids for resource_id in candidate_ids):
            return deterministic_fallback.model_copy(
                update={
                    "source": "deterministic_fallback",
                    "disclosure": "Untrusted matching output was discarded; deterministic suggestions are shown.",
                }
            )
        return result
    except (ValidationError, ValueError):
        return deterministic_fallback.model_copy(
            update={
                "source": "deterministic_fallback",
                "disclosure": "Untrusted matching output was discarded; deterministic suggestions are shown.",
            }
        )


def validate_resource_id(value: str) -> str:
    return str(UUID(value))
