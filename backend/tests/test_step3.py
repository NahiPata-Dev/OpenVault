from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import AccessContract, Booking, ResourceRequest, User
from app.seed import DEMO_USER_IDS, RESOURCE_IDS, SEED_OBJECT_IDS
from tests.conftest import login


def _interval(days: int, hours: int = 10) -> tuple[datetime, datetime]:
    start = (datetime.now(timezone.utc) + timedelta(days=days)).replace(
        hour=hours, minute=0, second=0, microsecond=0
    )
    return start, start + timedelta(hours=1)


def _submit_request(client, resource_id, start, end, purpose="project"):
    return client.post(
        "/api/requests",
        json={
            "resource_id": resource_id,
            "purpose": purpose,
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
        },
    )


def _manager_decision(client, request_id, outcome="approved", reason="Reviewed for demo."):
    return client.post(
        f"/api/requests/{request_id}/decision",
        json={"outcome": outcome, "reason": reason},
    )


def test_request_submission_persists_eligibility_result(requester_login):
    start, end = _interval(12)
    response = _submit_request(
        requester_login, RESOURCE_IDS["camera"], start, end
    )
    assert response.status_code == 201, response.text
    assert response.json()["request"]["status"] == "PENDING_REVIEW"
    with requester_login.app.state.session_factory() as session:
        persisted = session.get(ResourceRequest, response.json()["request"]["id"])
        assert persisted is not None
        assert persisted.requester_id == DEMO_USER_IDS["requester_a"]


def test_requester_cannot_approve_request(requester_login):
    start, end = _interval(13)
    submitted = _submit_request(requester_login, RESOURCE_IDS["camera"], start, end)
    request_id = submitted.json()["request"]["id"]
    response = _manager_decision(requester_login, request_id)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_self_approval_denied_for_manager_owned_request(manager_login):
    start, end = _interval(14)
    request_id = str(uuid4())
    with manager_login.app.state.session_factory() as session:
        session.add(
            ResourceRequest(
                id=request_id,
                requester_id=DEMO_USER_IDS["lab_manager"],
                resource_id=RESOURCE_IDS["camera"],
                purpose="Test setup self-approval.",
                start_at=start,
                end_at=end,
                status="PENDING_REVIEW",
                created_at=datetime.now(timezone.utc),
                is_demo=True,
            )
        )
        session.commit()
    response = _manager_decision(manager_login, request_id)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_approval_creates_booking_and_immutable_contract(manager_login, client):
    start, end = _interval(15)
    login(client, "requester_a")
    submitted = _submit_request(client, RESOURCE_IDS["camera"], start, end)
    request_id = submitted.json()["request"]["id"]
    login(manager_login, "lab_manager")

    approved = _manager_decision(manager_login, request_id)
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["booking"]["status"] == "CONFIRMED"
    contract_id = body["access_contract"]["id"]
    requirements_snapshot = body["access_contract"]["requirements_snapshot"]

    draft = manager_login.post(
        f"/api/resources/{RESOURCE_IDS['camera']}/policy-drafts",
        json={
            "structured_requirements": {
                "training_codes": ["NEW_REQUIREMENT"],
                "supervisor_required": True,
                "supervised_windows": [],
            },
            "allowed_uses": ["project"],
            "priority_policy": {},
        },
    )
    assert draft.status_code == 201, draft.text
    policy_version = draft.json()["policy"]["version"]
    activated = manager_login.post(
        f"/api/resources/{RESOURCE_IDS['camera']}/policies/{policy_version}/activate",
        json={"reason": "DEMO policy update."},
    )
    assert activated.status_code == 200, activated.text

    with manager_login.app.state.session_factory() as session:
        contract = session.get(AccessContract, contract_id)
        assert contract.requirements_snapshot == requirements_snapshot


def test_maintenance_hold_blocks_approval(manager_login):
    request_id = str(uuid4())
    start, end = _interval(16)
    with manager_login.app.state.session_factory() as session:
        session.add(
            ResourceRequest(
                id=request_id,
                requester_id=DEMO_USER_IDS["requester_a"],
                resource_id=RESOURCE_IDS["maintenance"],
                purpose="project",
                start_at=start,
                end_at=end,
                status="PENDING_REVIEW",
                created_at=datetime.now(timezone.utc),
                is_demo=True,
            )
        )
        session.commit()
    response = _manager_decision(manager_login, request_id)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ineligible"


def test_adjacent_slots_can_both_be_approved(manager_login):
    first_start, first_end = _interval(18)
    second_start = first_end
    second_end = second_start + timedelta(hours=1)
    ids = [_direct_pending(manager_login, DEMO_USER_IDS["requester_a"], first_start, first_end),
           _direct_pending(manager_login, DEMO_USER_IDS["requester_b"], second_start, second_end)]
    first = _manager_decision(manager_login, ids[0])
    second = _manager_decision(manager_login, ids[1])
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text


def test_overlapping_concurrent_approvals_create_at_most_one_booking(client):
    start, end = _interval(21)
    request_ids = [
        _direct_pending(client, DEMO_USER_IDS["requester_a"], start, end),
        _direct_pending(client, DEMO_USER_IDS["requester_b"], start, end),
    ]
    app = client.app
    first_client, second_client = TestClient(app), TestClient(app)
    login(first_client, "lab_manager")
    login(second_client, "lab_manager")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_manager_decision, first_client, request_ids[0]),
            pool.submit(_manager_decision, second_client, request_ids[1]),
        ]
        responses = [future.result() for future in futures]
    assert sum(response.status_code == 200 for response in responses) == 1
    assert all(response.status_code in {200, 409, 422} for response in responses)
    with client.app.state.session_factory() as session:
        count = session.scalar(
            select(Booking.id)
            .join(ResourceRequest, ResourceRequest.id == Booking.request_id)
            .where(
                ResourceRequest.resource_id == RESOURCE_IDS["camera"],
                Booking.start_at == start,
            )
        )
        assert count is not None
        bookings = session.scalars(
            select(Booking).where(Booking.start_at == start)
        ).all()
        assert len(bookings) == 1
    first_client.close()
    second_client.close()


def _direct_pending(client, requester_id, start, end):
    request_id = str(uuid4())
    with client.app.state.session_factory() as session:
        session.add(
            ResourceRequest(
                id=request_id,
                requester_id=requester_id,
                resource_id=RESOURCE_IDS["camera"],
                purpose="project",
                start_at=start,
                end_at=end,
                status="PENDING_REVIEW",
                created_at=datetime.now(timezone.utc),
                is_demo=True,
            )
        )
        session.commit()
    return request_id
