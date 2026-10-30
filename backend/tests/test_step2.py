from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.domain.allocation import rank_eligible_requests
from app.domain.eligibility import evaluate_eligibility
from app.domain.readiness import BLOCKER_ORDER, evaluate_readiness
from app.domain.state_transitions import apply_transition, validate_transition
from app.errors import APIError
from app.models import (
    AllocationDecision,
    AuditEvent,
    Resource,
    ResourcePolicy,
    User,
)
from app.seed import DEMO_USER_IDS, RESOURCE_IDS, SEED_OBJECT_IDS


def test_missing_training_blocks_request(client):
    with client.app.state.session_factory() as session:
        user = session.get(User, DEMO_USER_IDS["requester_c"])
        resource = session.get(Resource, RESOURCE_IDS["oscilloscope"])
        start = _next_weekday_interval()
        result = evaluate_eligibility(
            session, user, resource, start, start + timedelta(hours=1), "project"
        )
    assert [item["code"] for item in result["blockers"]] == ["missing_training"]


def test_expired_training_blocks_request(client):
    with client.app.state.session_factory() as session:
        user = session.get(User, DEMO_USER_IDS["requester_b"])
        resource = session.get(Resource, RESOURCE_IDS["oscilloscope"])
        record = user.training_records[0]
        record.valid_to = datetime.now(timezone.utc) - timedelta(days=1)
        session.commit()
        start = _next_weekday_interval()
        result = evaluate_readiness(session, user, resource, start, start + timedelta(hours=1))
    assert "missing_training" in {item["code"] for item in result["blockers"]}


def test_maintenance_hold_blocks_resource(client):
    with client.app.state.session_factory() as session:
        user = session.get(User, DEMO_USER_IDS["requester_a"])
        resource = session.get(Resource, RESOURCE_IDS["maintenance"])
        result = evaluate_readiness(session, user, resource)
    assert "maintenance_hold" in {item["code"] for item in result["blockers"]}


def test_supervisor_unavailable_blocks_request(client):
    with client.app.state.session_factory() as session:
        user = session.get(User, DEMO_USER_IDS["requester_a"])
        resource = session.get(Resource, RESOURCE_IDS["oscilloscope"])
        policy = session.scalar(
            select(ResourcePolicy).where(
                ResourcePolicy.resource_id == resource.id
            )
        )
        policy.structured_requirements = {
            "training_codes": ["OSCILLOSCOPE_SAFETY"],
            "supervisor_required": True,
            "supervised_windows": [],
        }
        session.commit()
        start = _next_weekday_interval()
        result = evaluate_readiness(session, user, resource, start, start + timedelta(hours=1))
    assert "supervisor_unavailable" in {item["code"] for item in result["blockers"]}


def test_all_blockers_returned_in_contract_order(client):
    with client.app.state.session_factory() as session:
        user = session.get(User, DEMO_USER_IDS["requester_c"])
        resource = session.get(Resource, RESOURCE_IDS["maintenance"])
        resource.weekly_operating_hours = []
        policy = session.scalar(
            select(ResourcePolicy).where(ResourcePolicy.resource_id == resource.id)
        )
        policy.structured_requirements = {
            "training_codes": ["UNRECORDED_TRAINING"],
            "supervisor_required": True,
            "supervised_windows": [],
        }
        session.commit()
        start = _next_weekday_interval()
        result = evaluate_readiness(session, user, resource, start, start + timedelta(hours=1))
    codes = [item["code"] for item in result["blockers"]]
    assert codes == [
        code
        for code in BLOCKER_ORDER
        if code in {
            "maintenance_hold",
            "missing_training",
            "supervisor_unavailable",
            "slot_conflict",
        }
    ]


def test_allocation_is_deterministic_and_snapshot_persists(client):
    now = datetime.now(timezone.utc)
    candidates = [
        {
            "request_id": "request-later",
            "requester_id": "requester-b",
            "created_at": now.isoformat(),
            "completed_bookings_30d": 1,
            "booked_hours_30d": 2,
        },
        {
            "request_id": "request-newcomer",
            "requester_id": "requester-a",
            "created_at": (now + timedelta(minutes=5)).isoformat(),
            "completed_bookings_30d": 0,
            "booked_hours_30d": 0,
        },
    ]
    first = rank_eligible_requests(candidates, now)
    assert first == rank_eligible_requests(list(reversed(candidates)), now)
    assert first["ranked_request_ids"][0] == "request-newcomer"

    with client.app.state.session_factory() as session:
        decision = AllocationDecision(
            id=str(uuid4()),
            request_id=SEED_OBJECT_IDS["request:waitlisted"],
            decision_sequence=2,
            policy_version=SEED_OBJECT_IDS["policy:camera"],
            outcome="waitlisted",
            explanation_code=first["recommendation"],
            explanation="Deterministic allocation snapshot test.",
            inputs_snapshot=first["inputs_snapshot"],
            reviewer_id=DEMO_USER_IDS["lab_manager"],
            created_at=now,
            is_demo=True,
        )
        session.add(decision)
        session.commit()
        persisted = session.get(AllocationDecision, decision.id)
        assert persisted.inputs_snapshot == first["inputs_snapshot"]


@pytest.mark.parametrize(
    ("entity_type", "current", "target"),
    [
        ("request", "CLOSED", "APPROVED"),
        ("booking", "CANCELLED", "CHECKED_IN"),
        ("incident", "RESOLVED", "UNDER_REVIEW"),
    ],
)
def test_invalid_transitions_are_rejected(entity_type, current, target):
    with pytest.raises(APIError) as error:
        validate_transition(entity_type, current, target)
    assert error.value.code == "invalid_state"
    assert error.value.status_code == 409


def test_transition_creates_audit_event_in_same_session(client):
    with client.app.state.session_factory() as session:
        from app.models import ResourceRequest

        request = session.get(ResourceRequest, SEED_OBJECT_IDS["request:pending"])
        actor = session.get(User, DEMO_USER_IDS["lab_manager"])
        apply_transition(
            session,
            request,
            "request",
            "APPROVED",
            actor,
            request_id="step2-test",
        )
        session.flush()
        event = session.scalar(
            select(AuditEvent).where(AuditEvent.request_id == "step2-test")
        )
        assert event is not None
        assert event.action == "request.approved"


def _next_weekday_interval() -> datetime:
    now = datetime.now(timezone.utc)
    days_until_monday = (7 - now.weekday()) % 7 or 7
    return (now + timedelta(days=days_until_monday)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
