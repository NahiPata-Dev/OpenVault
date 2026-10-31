import re
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.eligibility import evaluate_eligibility
from app.domain.readiness import active_policy, evaluate_readiness
from app.errors import APIError
from app.models import Resource, ResourceRequest, User
from app.schemas.assistant import (
    AssistantChatResponse,
    AssistantDraftRequest,
    AssistantEligibilityItem,
    AssistantResourceEligibility,
    AssistantSuggestion,
)

IST = ZoneInfo("Asia/Kolkata")
STOP_WORDS = {
    "a", "an", "and", "any", "at", "can", "find", "for", "from", "get",
    "have", "in", "is", "it", "me", "my", "need", "of", "on", "or",
    "please", "resource", "resources", "show", "some", "the", "to", "use",
    "want", "with", "would",
}
INTENT_WORDS = {
    "alternative", "alternatives", "approved", "approval", "book", "booking",
    "check", "draft", "eligible", "eligibility", "explain", "my", "need",
    "prepare", "rejected", "requirement", "requirements", "rules", "training",
    "waitlisted", "why",
}
ALLOWED_USES = ("project", "coursework", "research")


@dataclass(frozen=True)
class ParsedSlot:
    start: datetime | None
    end: datetime | None
    missing: tuple[str, ...]


@dataclass
class AssistantResult:
    response: AssistantChatResponse
    intent: str


def determine_intent(message: str) -> str:
    value = message.casefold()
    if re.search(
        r"\b(pay|paying|payment|payments|charge|charging|purchase|fee|fees|cost|price|pricing)\b",
        value,
    ):
        return "unsupported_payments"
    if re.search(
        r"\b(override|bypass|ignore|skip)\b.{0,50}\b"
        r"(rule|training|policy|eligibility|approval|access|availability|restriction)s?\b",
        value,
    ):
        return "unsupported_override"
    if re.search(r"\b(why|explain)\b", value) and re.search(
        r"\b(my|request|approved|rejected|waitlist|waitlisted)\b", value
    ):
        return "explain_request"
    if re.search(r"\b(alternative|alternatives|instead)\b", value):
        return "show_alternatives"
    if re.search(r"\b(eligibility|eligible|can i use|am i allowed)\b", value):
        return "check_eligibility"
    if re.search(r"\b(requirements?|what do i need|training|supervision|rules)\b", value):
        return "explain_requirements"
    if re.search(r"\b(draft|prepare|book|booking|request)\b", value):
        return "prepare_draft"
    search_hints = {
        "equipment",
        "find",
        "lab",
        "machine",
        "need",
        "resource",
        "resources",
        "search",
        "tool",
        "want",
    }
    if not (_words(value) & search_hints) and not re.search(
        r"\b(find|search|browse|show)\b.*\b(resources?|equipment|tools?)\b|"
        r"\b(laser|cutter|gpu|printer|oscilloscope|microscope|cnc|drone|"
        r"workstation|studio|bench|room|hyderabad|bengaluru|chennai|pune|"
        r"mumbai|noida|kolkata)\b",
        value,
    ):
        return "general_help"
    return "find_resources"


def parse_slot(message: str, now: datetime | None = None) -> ParsedSlot:
    local_now = (now or datetime.now(IST)).astimezone(IST)
    value = message.casefold()
    selected_date: date | None = None
    if re.search(r"\bday after tomorrow\b", value):
        selected_date = local_now.date() + timedelta(days=2)
    elif re.search(r"\btomorrow\b", value):
        selected_date = local_now.date() + timedelta(days=1)
    elif re.search(r"\btoday\b", value):
        selected_date = local_now.date()
    elif day_count_match := re.search(r"\bin\s+(\d+)\s+days?\b", value):
        days = int(day_count_match.group(1))
        selected_date = local_now.date() + timedelta(days=days)
    elif weekday_match := re.search(
        r"\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        value,
    ):
        weekday = (
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday",
        ).index(weekday_match.group(1))
        days = (weekday - local_now.weekday()) % 7 or 7
        selected_date = local_now.date() + timedelta(days=days)
    else:
        date_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", value)
        if date_match:
            try:
                selected_date = date(
                    int(date_match.group(1)),
                    int(date_match.group(2)),
                    int(date_match.group(3)),
                )
            except ValueError:
                selected_date = None

    time_matches = list(
        re.finditer(
            r"\b(1[0-2]|0?[1-9])(?::([0-5]\d))?\s*(am|pm)\b"
            r"|\b([01]?\d|2[0-3]):([0-5]\d)\b",
            value,
        )
    )
    parsed_times = [_parse_time_match(match) for match in time_matches]
    has_explicit_end = len(parsed_times) > 1 and bool(
        re.search(
            r"\b(to|until|through)\b|[-–]",
            value[time_matches[0].end():time_matches[1].start()],
        )
    )
    start: datetime | None = None
    end: datetime | None = None
    if selected_date is not None and parsed_times:
        start = datetime.combine(selected_date, parsed_times[0], tzinfo=IST)
        if has_explicit_end:
            end_date = selected_date
            end = datetime.combine(end_date, parsed_times[1], tzinfo=IST)
            if end <= start:
                end += timedelta(days=1)
        else:
            duration_match = re.search(
                r"\bfor\s+(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)\b",
                value,
            )
            if duration_match:
                duration = float(duration_match.group(1))
                unit = duration_match.group(2)
                end = start + timedelta(
                    minutes=duration * (60 if unit.startswith(("h", "hr")) else 1)
                )

    missing: list[str] = []
    if selected_date is None:
        missing.append("date")
    if not parsed_times:
        missing.append("start time")
    elif end is None and not has_explicit_end:
        missing.append("end time or session duration")
    return ParsedSlot(start=start, end=end, missing=tuple(missing))


def _parse_time_match(match: re.Match[str]) -> datetime_time:
    if match.group(3):
        hour = int(match.group(1)) % 12
        if match.group(3) == "pm":
            hour += 12
        return datetime_time(hour, int(match.group(2) or 0))
    return datetime_time(int(match.group(4)), int(match.group(5)))


def run_rules(
    session: Session,
    user: User,
    message: str,
    request_id: str,
    intent_override: str | None = None,
    model_resource_ids: set[str] | None = None,
    model_reply: str | None = None,
    source: Literal["model", "rules"] = "rules",
) -> AssistantResult:
    intent = determine_intent(message)
    if intent.startswith("unsupported_"):
        answer = (
            "Payments are not processed in this prototype. Ask the institution's "
            "administrator about any access costs."
            if intent == "unsupported_payments"
            else "I can't override training, eligibility, or approval rules. Ask the "
            "resource manager or authorized training owner for help."
        )
        return _result(answer, [], [], None, _quick_actions(intent), source, request_id, intent)

    if intent == "general_help":
        answer = (
            "Hi! I can help find equipment by type or city, explain access "
            "requirements, check your eligibility, or prepare a request for your "
            "review. What would you like to use, and where?"
        )
        return _result(
            answer,
            [],
            [],
            None,
            _quick_actions(intent),
            source,
            request_id,
            intent,
        )

    if intent_override and not intent.startswith("unsupported_"):
        intent = _mapped_model_intent(intent_override, intent)

    if intent == "explain_request":
        answer = explain_own_request(session, user, message)
        return _result(answer, [], [], None, _quick_actions(intent), source, request_id, intent)

    resources = scoped_resources(session, user)
    if not resources:
        answer = (
            "There are no resources in this account's catalog yet. Ask your "
            "institution's manager to publish or seed the sample catalog, then try again."
        )
        return _result(
            answer,
            [],
            [],
            None,
            _quick_actions("general_help"),
            source,
            request_id,
            intent,
        )
    slot = parse_slot(message)
    candidates = [
        resource
        for resource in find_candidates(resources, message)
        if _matches_hard_filters(resource, resources, message)
    ]

    if intent == "show_alternatives":
        original = _find_referenced_resource(resources, message)
        if original:
            alternatives = [
                resource
                for resource in _alternative_candidates(resources, original)
                if _matches_hard_filters(resource, resources, message)
            ]
            candidates = alternatives or [
                resource
                for resource in resources
                if resource.id != original.id
                and resource.status == "active"
                and _matches_hard_filters(resource, resources, message)
            ]

    if intent == "prepare_draft" and user.role != "requester":
        visible = candidates[:10]
        eligibility = _eligibility_for(
            session, user, visible, slot, _purpose_and_use(message)[1]
        )
        return _result(
            "Only requester accounts can submit access requests. Sign in with a "
            "requester account to prepare and submit a request.",
            visible,
            eligibility,
            None,
            ["Find resources", "Check my eligibility"],
            source,
            request_id,
            intent,
            model_reply if source == "model" else None,
        )

    candidates = [
        resource
        for resource in candidates
        if _matches_hard_filters(resource, resources, message)
    ]
    if model_resource_ids is not None:
        candidates = [
            resource
            for resource in resources
            if resource.id in model_resource_ids
            and _matches_hard_filters(resource, resources, message)
        ]

    draft: AssistantDraftRequest | None = None
    if intent == "prepare_draft":
        draft, clarification = _prepare_draft(
            session, message, candidates, slot
        )
        if clarification:
            return _result(
                clarification,
                candidates[:10],
                _eligibility_for(
                    session, user, candidates[:10], slot, _purpose_and_use(message)[1]
                ),
                None,
                _quick_actions(intent),
                source,
                request_id,
                intent,
                model_reply if source == "model" else None,
            )

    visible = candidates[:10]
    eligibility = _eligibility_for(
        session, user, visible, slot, _purpose_and_use(message)[1]
    )
    reply = _reply_for(session, intent, visible, draft)
    return _result(
        reply,
        visible,
        eligibility,
        draft,
        _quick_actions(intent),
        source,
        request_id,
        intent,
        model_reply if source == "model" else None,
    )


def scoped_resources(session: Session, user: User) -> list[Resource]:
    query = select(Resource).options(joinedload(Resource.owner)).order_by(Resource.name)
    if user.role == "lab_manager":
        query = query.where(Resource.owner.has(organization_id=user.organization_id))
    return [
        resource
        for resource in session.scalars(query).unique().all()
        if resource.status != "retired"
    ]


def _words(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if len(token) > 1 and token not in STOP_WORDS and token not in INTENT_WORDS
    }


def find_candidates(resources: list[Resource], message: str) -> list[Resource]:
    value = message.casefold()
    cities = {resource.city.casefold() for resource in resources if resource.city}
    areas = {resource.area.casefold() for resource in resources if resource.area}
    matched_cities = {city for city in cities if city in value}
    matched_areas = {area for area in areas if area in value}
    categories = {resource.category.casefold() for resource in resources}
    matched_categories = {category for category in categories if category in value}

    candidates = resources
    if matched_cities:
        candidates = [resource for resource in candidates if resource.city.casefold() in matched_cities]
    if matched_areas:
        candidates = [resource for resource in candidates if resource.area.casefold() in matched_areas]
    if matched_categories:
        candidates = [resource for resource in candidates if resource.category.casefold() in matched_categories]

    query_terms = _words(message)
    for location in matched_cities | matched_areas:
        query_terms -= _words(location)
    if not query_terms:
        return candidates

    scored: list[tuple[int, Resource]] = []
    for resource in candidates:
        searchable = _words(
            " ".join(
                [
                    resource.name,
                    resource.category,
                    resource.location,
                    resource.city,
                    resource.area,
                    *resource.capability_tags,
                    *resource.allowed_uses,
                ]
            )
        )
        overlap = query_terms & searchable
        if overlap:
            scored.append((len(overlap), resource))
    return [
        resource
        for _score, resource in sorted(
            scored,
            key=lambda entry: (-entry[0], entry[1].name.casefold()),
        )
    ]


def _matches_hard_filters(
    resource: Resource,
    scoped: list[Resource],
    message: str,
) -> bool:
    value = message.casefold()
    cities = {item.city.casefold() for item in scoped if item.city}
    areas = {item.area.casefold() for item in scoped if item.area}
    categories = {item.category.casefold() for item in scoped}
    selected_cities = {city for city in cities if city in value}
    selected_areas = {area for area in areas if area in value}
    selected_categories = {category for category in categories if category in value}
    if selected_cities and resource.city.casefold() not in selected_cities:
        return False
    if selected_areas and resource.area.casefold() not in selected_areas:
        return False
    if selected_categories and resource.category.casefold() not in selected_categories:
        return False
    if re.search(r"\b(active|available)\b", value):
        return resource.status == "active"
    if re.search(r"\b(maintenance|on hold)\b", value):
        return resource.status == "maintenance_hold"
    return resource.status != "retired"


def _find_referenced_resource(
    resources: list[Resource], message: str
) -> Resource | None:
    value = message.casefold()
    identifier = re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
        value,
    )
    if identifier:
        return next(
            (resource for resource in resources if resource.id.casefold() == identifier.group()),
            None,
        )
    matches = [
        resource for resource in resources
        if resource.name.casefold() in value
    ]
    return max(matches, key=lambda resource: len(resource.name), default=None)


def _alternative_candidates(
    resources: list[Resource], original: Resource
) -> list[Resource]:
    terms = _words(" ".join([original.category, *original.capability_tags]))
    matches = [
        resource for resource in resources
        if resource.id != original.id
        and resource.status == "active"
        and (
            resource.category.casefold() == original.category.casefold()
            or terms & _words(
                " ".join([resource.name, resource.category, *resource.capability_tags])
            )
        )
    ]
    return sorted(matches, key=lambda resource: resource.name.casefold())


def _prepare_draft(
    session: Session,
    message: str,
    candidates: list[Resource],
    slot: ParsedSlot,
) -> tuple[AssistantDraftRequest | None, str | None]:
    selected = _find_referenced_resource(candidates, message)
    if selected is None and len(candidates) == 1:
        selected = candidates[0]
    if selected is None:
        return None, "Which resource should I use for the draft?"

    if slot.start is None or slot.end is None:
        return None, _slot_clarification(slot)

    purpose, allowed_use = _purpose_and_use(message)
    if purpose is None or allowed_use is None:
        return None, "What is the purpose of the session, and is it for a project, coursework, or research?"

    policy = active_policy(session, selected.id)
    allowed_uses = policy.allowed_uses if policy else []
    if allowed_use not in allowed_uses:
        return None, f"{selected.name} does not list {allowed_use} as an allowed use. Which listed use should I use?"

    if slot.start <= datetime.now(IST):
        return None, "What future date and time should I use for the draft?"

    return (
        AssistantDraftRequest(
            resource_id=selected.id,
            start=slot.start,
            end=slot.end,
            purpose=purpose,
            allowed_use=allowed_use,
        ),
        None,
    )


def _slot_clarification(slot: ParsedSlot) -> str:
    missing = set(slot.missing)
    if missing == {"date"}:
        return "What date should I use for those times?"
    if "date" in missing and "start time" in missing:
        return "What date and start/end time should I use? Include the session duration."
    if "date" in missing:
        return "What date and end time or session duration should I use for the start time?"
    if "start time" in missing:
        return "What start time should I use for that date? Include the session duration or end time."
    return "What end time or session duration should I use for the date and start time provided?"


def _purpose_and_use(message: str) -> tuple[str | None, str | None]:
    value = message.casefold()
    uses = [use for use in ALLOWED_USES if re.search(rf"\b{use}\b", value)]
    return (uses[0], uses[0]) if len(uses) == 1 else (None, None)


def _eligibility_for(
    session: Session,
    user: User,
    resources: list[Resource],
    slot: ParsedSlot,
    purpose: str | None,
) -> list[AssistantResourceEligibility]:
    results: list[AssistantResourceEligibility] = []
    for resource in resources:
        policy = active_policy(session, resource.id)
        requirements = policy.structured_requirements if policy else {}
        training_codes = requirements.get("training_codes", [])
        policy_blocker: AssistantEligibilityItem | None = None
        try:
            readiness = evaluate_eligibility(
                session, user, resource, slot.start, slot.end, purpose
            )
        except APIError as error:
            if error.code != "validation_error":
                raise
            next_action = (
                "Choose one of the resource's allowed uses."
                if "purpose is not permitted" in error.message
                else "Choose a shorter session within the resource's booking rules."
                if "maximum duration" in error.message
                else "Choose a date within the resource's advance-booking window."
                if "advance-booking window" in error.message
                else "Review the resource's booking rules or ask its manager."
            )
            policy_blocker = AssistantEligibilityItem(
                requirement=error.message,
                status="fail",
                next_action=next_action,
            )
            readiness = evaluate_readiness(
                session, user, resource, slot.start, slot.end
            )
        blockers_by_code = {
            blocker["code"]: blocker for blocker in readiness["blockers"]
        }
        missing_codes = set(
            blockers_by_code.get("missing_training", {}).get(
                "requirement_codes", []
            )
        )
        items = [
            AssistantEligibilityItem(
                requirement=(
                    f"Training {training_code} is missing, expired, or not verified."
                    if training_code in missing_codes
                    else f"Training {training_code} is verified and current."
                ),
                status="fail" if training_code in missing_codes else "pass",
                next_action=(
                    "Ask the authorized training owner to record a verified sign-off."
                    if training_code in missing_codes
                    else "No action needed."
                ),
            )
            for training_code in training_codes
        ]
        if policy_blocker:
            items.append(policy_blocker)
        for blocker in readiness["blockers"]:
            code = blocker["code"]
            if code == "missing_training":
                continue
            message = blocker["message"]
            if code == "slot_conflict" and slot.start and slot.end:
                operating_hours = _format_windows(resource.weekly_operating_hours)
                message = (
                    f"Requested slot {slot.start.strftime('%Y-%m-%d %H:%M')}–"
                    f"{slot.end.strftime('%H:%M')} IST is outside operating hours "
                    f"or conflicts with a confirmed booking. Listed operating "
                    f"hours: {operating_hours or 'none'}."
                )
            elif code == "supervisor_unavailable" and slot.start and slot.end:
                supervised_hours = _format_windows(
                    requirements.get("supervised_windows", [])
                )
                message = (
                    f"Supervisor coverage is not listed for "
                    f"{slot.start.strftime('%Y-%m-%d %H:%M')}–"
                    f"{slot.end.strftime('%H:%M')} IST. Supervised windows: "
                    f"{supervised_hours or 'none'}."
                )
            items.append(
                AssistantEligibilityItem(
                    requirement=message,
                    status="fail",
                    next_action=blocker["next_action"],
                )
            )
        if resource.status == "active" and not any(
            blocker["code"] in {"maintenance_hold", "resource_retired"}
            for blocker in readiness["blockers"]
        ):
            items.append(
                AssistantEligibilityItem(
                    requirement="Resource is active.",
                    status="pass",
                    next_action="No action needed for resource status.",
                )
            )
        if not items:
            items.append(
                AssistantEligibilityItem(
                    requirement="Resource booking requirements",
                    status="pass",
                    next_action="You can submit a request for manager review.",
                )
            )
        results.append(
            AssistantResourceEligibility(resource_id=resource.id, items=items)
        )
    return results


def _format_windows(windows: list[dict]) -> str:
    weekday_names = (
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    )
    return "; ".join(
        f"{weekday_names[window['weekday'] - 1]} {window['start']}–{window['end']} IST"
        for window in windows
        if 1 <= window.get("weekday", 0) <= 7
        and window.get("start")
        and window.get("end")
    )


def _reply_for(
    session: Session,
    intent: str,
    resources: list[Resource],
    draft: AssistantDraftRequest | None,
) -> str:
    if intent == "prepare_draft" and draft is not None:
        return (
            "Draft prepared for your review only. Nothing has been submitted; use "
            "the existing request form to submit it."
        )
    if not resources:
        return (
            "I couldn't find a close match in your catalog. Try a resource type, "
            "a city or area, or what you want to make—for example, "
            "\"laser cutter in Hyderabad\" or \"GPU workstation for machine learning\"."
        )
    if intent == "explain_requirements":
        return _requirements_reply(session, resources)
    if intent == "check_eligibility":
        return "Here are your current readiness checks. Slot-specific availability is checked when you provide a date and time."
    if intent == "show_alternatives":
        return "Here are alternative resources in your available catalog. Review each resource's requirements before requesting access."
    if intent == "prepare_draft":
        return "I can prepare a draft after one missing detail is clarified."
    count = len(resources)
    return f"I found {count} matching resource{'s' if count != 1 else ''}. Review their eligibility and access requirements before requesting."


def _requirements_reply(session: Session, resources: list[Resource]) -> str:
    summaries = []
    for resource in resources:
        policy = active_policy(session, resource.id)
        structured = policy.structured_requirements if policy else {}
        trainings = structured.get("training_codes", [])
        allowed_uses = policy.allowed_uses if policy else resource.allowed_uses
        supervision = (
            _format_windows(structured.get("supervised_windows", []))
            if structured.get("supervisor_required")
            else "not required"
        )
        summaries.append(
            f"{resource.name}: training {', '.join(trainings) if trainings else 'none listed'}; "
            f"allowed uses {', '.join(allowed_uses) if allowed_uses else 'not listed'}; "
            f"who can use it {', '.join(resource.who_can_use) if resource.who_can_use else 'not listed'}; "
            f"supervision {supervision}."
        )
    return " ".join(summaries)


def explain_own_request(session: Session, user: User, message: str) -> str:
    rows = session.scalars(
        select(ResourceRequest)
        .options(
            joinedload(ResourceRequest.resource),
            joinedload(ResourceRequest.decisions),
        )
        .where(ResourceRequest.requester_id == user.id)
        .order_by(ResourceRequest.created_at.desc())
        .limit(100)
    ).unique().all()
    if not rows:
        return "I couldn't find any requests associated with your account."

    value = message.casefold()
    request_id = re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
        value,
    )
    if request_id:
        rows = [row for row in rows if row.id.casefold() == request_id.group()]
    else:
        resource_matches = [
            row for row in rows if row.resource.name.casefold() in value
        ]
        if resource_matches:
            rows = resource_matches
        elif any(status in value for status in ("approved", "rejected", "waitlisted")):
            requested_status = next(
                status for status in ("waitlisted", "approved", "rejected") if status in value
            )
            rows = [
                row for row in rows
                if row.status.casefold() == requested_status
            ]
    if not rows:
        return "I couldn't find that request in your account's request history."

    row = rows[0]
    decision = max(
        row.decisions,
        key=lambda item: item.decision_sequence,
        default=None,
    )
    if decision:
        reason = decision.explanation.strip()
        return (
            f"Your request for {row.resource.name} is {row.status}. "
            f"Recorded decision: {reason}"
        )
    if row.status == "INELIGIBLE":
        return (
            f"Your request for {row.resource.name} is marked ineligible. "
            "Review the resource requirements and your training records, then contact "
            "the resource manager or authorized training owner."
        )
    return f"Your request for {row.resource.name} is currently {row.status} and has no recorded manager decision yet."


def _mapped_model_intent(model_intent: str, rules_intent: str) -> str:
    if model_intent in {
        "find_resources",
        "explain_requirements",
        "check_eligibility",
        "show_alternatives",
        "explain_request",
        "prepare_draft",
    }:
        return model_intent
    return rules_intent


def _quick_actions(intent: str) -> list[str]:
    if intent == "general_help":
        return [
            "Find a laser cutter in Hyderabad",
            "Check my eligibility",
            "Prepare a request draft",
        ]
    if intent == "prepare_draft":
        return ["Check eligibility", "Find another resource"]
    if intent == "explain_request":
        return ["Find resources", "Check my eligibility"]
    return ["Check my eligibility", "Show alternatives", "Prepare a draft"]


def _result(
    reply: str,
    resources: list[Resource],
    eligibility: list[AssistantResourceEligibility],
    draft: AssistantDraftRequest | None,
    quick_actions: list[str],
    source: Literal["model", "rules"],
    request_id: str,
    intent: str,
    model_reply: str | None = None,
) -> AssistantResult:
    if model_reply and resources and intent in {"find_resources", "show_alternatives"}:
        reply = model_reply.strip() or reply
    eligible_by_id = {str(item.resource_id): item for item in eligibility}
    suggestions = [
        AssistantSuggestion(
            resource_id=resource.id,
            reason=_suggestion_reason(resource, eligible_by_id.get(resource.id)),
        )
        for resource in resources
    ]
    response = AssistantChatResponse(
        reply_text=reply,
        suggestions=suggestions,
        eligibility=eligibility,
        draft_request=draft,
        quick_actions=quick_actions,
        source=source,
        request_id=request_id,
    )
    return AssistantResult(response, intent)


def _suggestion_reason(
    resource: Resource,
    eligibility: AssistantResourceEligibility | None,
) -> str:
    reason = f"{resource.name} in {resource.city or resource.location}"
    if eligibility:
        failed = next(
            (item for item in eligibility.items if item.status == "fail"),
            None,
        )
        if failed:
            reason += f"; {failed.requirement}"
    reason = " ".join(reason.split())
    if len(reason) > 240:
        reason = reason[:237].rstrip() + "..."
    return reason
