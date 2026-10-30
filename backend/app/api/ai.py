from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.dependencies import require_roles
from app.domain.readiness import evaluate_readiness
from app.errors import raise_api_error
from app.models import Resource, User
from app.schemas import (
    MatchCandidate,
    ResourceMatchRequest,
    ResourceMatchResult,
)
from app.services.ai_provider import validate_provider_result

router = APIRouter(prefix="/api/ai", tags=["resource-matching"])
MATCHING_DISCLOSURE = (
    "Deterministic resource suggestions only; backend eligibility and booking rules still apply."
)


@router.post("/match")
def match_resources(
    payload: ResourceMatchRequest,
    session: Session = Depends(get_session),
    user: User = Depends(
        require_roles("requester", "lab_manager", "institution_admin")
    ),
) -> dict:
    constraints = payload.constraints
    if (constraints.available_from is None) != (constraints.available_to is None):
        raise_api_error("validation_error", "Availability timestamps must be paired.", 422)
    resources = session.scalars(
        select(Resource)
        .where(Resource.owner.has(organization_id=user.organization_id))
        .order_by(Resource.name)
    ).all()
    categories = {value.casefold() for value in constraints.categories}
    capabilities = {value.casefold() for value in constraints.capabilities}
    goal_terms = {
        term.casefold()
        for term in payload.goal.split()
        if len(term) > 2
    }
    candidates = []
    for resource in resources:
        if categories and resource.category.casefold() not in categories:
            continue
        tags = [tag.casefold() for tag in resource.capability_tags]
        if capabilities and not any(
            capability in tag for capability in capabilities for tag in tags
        ):
            continue
        content = " ".join(
            [resource.name, resource.category, resource.location, *resource.capability_tags]
        ).casefold()
        if goal_terms and not any(term in content for term in goal_terms) and not categories and not capabilities:
            continue
        readiness = evaluate_readiness(
            session,
            user,
            resource,
            constraints.available_from,
            constraints.available_to,
        )
        blocker_text = (
            " Readiness blockers: " + ", ".join(item["code"] for item in readiness["blockers"])
            if readiness["blockers"]
            else ""
        )
        candidates.append(
            MatchCandidate(
                resource_id=resource.id,
                explanation=f"Matched deterministic resource keywords.{blocker_text}",
            )
        )
    result = ResourceMatchResult(
        criteria={
            "categories": sorted(categories),
            "capabilities": sorted(capabilities),
        },
        candidates=candidates,
        source="deterministic",
        disclosure=MATCHING_DISCLOSURE,
    )
    allowed_ids = {str(candidate.resource_id) for candidate in candidates}
    validated = validate_provider_result(
        result.model_dump(mode="json"),
        allowed_ids,
        result,
    )
    return validated.model_dump(mode="json")
