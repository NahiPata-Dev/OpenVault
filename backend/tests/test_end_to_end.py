from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.seed import DEMO_USER_IDS, RESOURCE_IDS

PASSWORD = "test-demo-password"
CHECKLIST_VERSION = "northstar-condition-v1"

CHECK_IN = {
    "checklist_version": CHECKLIST_VERSION,
    "condition": {
        "physical_condition": "ok",
        "accessories_complete": "yes",
        "functional_test": "works",
        "notes": "Initial condition recorded.",
    },
    "evidence_references": [],
}

CHECK_OUT_WITH_DISCREPANCY = {
    "checklist_version": CHECKLIST_VERSION,
    "condition": {
        "physical_condition": "minor_wear",
        "accessories_complete": "yes",
        "functional_test": "works",
        "notes": "Return condition recorded for review.",
    },
    "evidence_references": [],
}


def _login(client: TestClient, account: str) -> dict:
    response = client.post(
        "/api/auth/demo-login",
        json={"account_id": DEMO_USER_IDS[account], "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["user"]


def _interval(start: datetime) -> dict:
    return {
        "start_at": start.isoformat(),
        "end_at": (start + timedelta(hours=1)).isoformat(),
    }


def _submit_request(
    client: TestClient, resource_id: str, interval: dict
) -> dict:
    response = client.post(
        "/api/requests",
        json={
            "resource_id": resource_id,
            "purpose": "project",
            **interval,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_complete_requester_manager_incident_journey_and_waitlist(
    client: TestClient,
) -> None:
    requester = _login(client, "requester_a")
    assert requester["display_name"] == "Requester A"

    discovered = client.get("/api/resources", params={"query": "oscilloscope"})
    assert discovered.status_code == 200, discovered.text
    station = next(
        item
        for item in discovered.json()["items"]
        if item["id"] == RESOURCE_IDS["oscilloscope"]
    )
    assert station["name"] == "Oscilloscope Training Station"

    oscilloscope_start = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    oscilloscope_start -= timedelta(minutes=2)
    submitted = _submit_request(
        client,
        RESOURCE_IDS["oscilloscope"],
        _interval(oscilloscope_start),
    )
    request_id = submitted["request"]["id"]
    assert submitted["request"]["status"] == "PENDING_REVIEW"
    assert submitted["eligibility"]["eligible"] is True
    assert submitted["eligibility"]["blockers"] == []

    manager = _login(client, "lab_manager")
    assert manager["display_name"] == "Lab Manager"
    queue = client.get("/api/manager/requests")
    assert queue.status_code == 200, queue.text
    queued_request = next(
        item for item in queue.json()["items"] if item["request"]["id"] == request_id
    )
    assert queued_request["eligibility"]["eligible"] is True
    assert queued_request["eligibility"]["blockers"] == []
    assert queued_request["allocation_recommendation"]["recommendation"]
    assert queued_request["allocation_recommendation"]["inputs_snapshot"]

    approval_reason = "Approved after verifying training, coverage, and availability."
    approved = client.post(
        f"/api/requests/{request_id}/decision",
        json={"outcome": "approved", "reason": approval_reason},
    )
    assert approved.status_code == 200, approved.text
    approval_body = approved.json()
    booking = approval_body["booking"]
    assert booking["status"] == "CONFIRMED"
    contract = approval_body["access_contract"]
    assert contract is not None
    assert contract["status"] == "ACTIVE"
    assert contract["booking_id"] == booking["id"]
    assert contract["policy_version_id"]
    assert contract["requirements_snapshot"]["training_codes"] == ["OSCILLOSCOPE_SAFETY"]

    _login(client, "requester_a")
    history = client.get("/api/requests/mine")
    assert history.status_code == 200, history.text
    persisted = next(
        item for item in history.json()["items"] if item["request"]["id"] == request_id
    )
    assert persisted["booking"]["id"] == booking["id"]
    assert persisted["access_contract"]["id"] == contract["id"]
    assert approval_reason in persisted["decision"]["explanation"]

    check_in = client.post(
        f"/api/bookings/{booking['id']}/check-in",
        json=CHECK_IN,
    )
    assert check_in.status_code == 200, check_in.text
    assert check_in.json()["booking"]["status"] == "CHECKED_IN"
    assert check_in.json()["handover_report"]["stage"] == "IN"

    check_out = client.post(
        f"/api/bookings/{booking['id']}/check-out",
        json=CHECK_OUT_WITH_DISCREPANCY,
    )
    assert check_out.status_code == 200, check_out.text
    check_out_body = check_out.json()
    assert check_out_body["booking"]["status"] == "INCIDENT_REVIEW"
    assert check_out_body["handover_report"]["stage"] == "OUT"
    incident = check_out_body["incident"]
    assert incident is not None
    assert incident["category"] == "damage"
    assert "blame" not in incident["description"].casefold()
    incident_id = incident["id"]

    _login(client, "lab_manager")
    detail = client.get(f"/api/incidents/{incident_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["incident"]["status"] == "OPEN"

    response_message = "The return checklist has been reviewed; no attribution is made."
    response = client.post(
        f"/api/incidents/{incident_id}/responses",
        json={"message": response_message},
    )
    assert response.status_code == 201, response.text
    assert response_message in [
        item["message"] for item in response.json()["incident"]["responses"]
    ]

    review = client.post(
        f"/api/incidents/{incident_id}/review",
        json={"status": "under_review", "reason": "Reviewing the reported condition."},
    )
    assert review.status_code == 200, review.text
    rationale = "The reported minor wear was reviewed against both handover checklists."
    resolution = client.post(
        f"/api/incidents/{incident_id}/resolve",
        json={"outcome": "resolved", "rationale": rationale},
    )
    assert resolution.status_code == 200, resolution.text
    assert resolution.json()["incident"]["status"] == "RESOLVED"
    assert resolution.json()["incident"]["resolution"]["rationale"] == rationale

    _login(client, "requester_a")
    refreshed = client.get("/api/requests/mine")
    assert refreshed.status_code == 200, refreshed.text
    final_record = next(
        item for item in refreshed.json()["items"] if item["request"]["id"] == request_id
    )
    assert final_record["booking"]["status"] == "CLOSED"
    assert final_record["access_contract"]["status"] == "COMPLETED"

    timeline = client.get(
        f"/api/resources/{RESOURCE_IDS['oscilloscope']}/timeline"
    )
    assert timeline.status_code == 200, timeline.text
    events = timeline.json()["items"]
    actions = [item["event"] for item in events]
    required_actions = [
        "request.submitted",
        "request.queued_for_review",
        "request.approved",
        "booking.confirmed",
        "booking.checked_in",
        "booking.checked_out",
        "incident.opened",
        "booking.incident_review_opened",
        "incident.response_added",
        "incident.review_started",
        "incident.resolved",
        "booking.closed_after_review",
    ]
    positions = [actions.index(action) for action in required_actions]
    assert positions == sorted(positions), actions
    timestamps = [datetime.fromisoformat(item["timestamp"]) for item in events]
    assert timestamps == sorted(timestamps), timestamps

    # Exercise the competing-request path on an unused resource and slot.
    competition_start = datetime.now(timezone.utc) + timedelta(days=1)
    competition_start = competition_start.replace(second=0, microsecond=0)
    _login(client, "requester_a")
    first_competitor = _submit_request(
        client, RESOURCE_IDS["bench"], _interval(competition_start)
    )
    _login(client, "requester_b")
    second_competitor = _submit_request(
        client, RESOURCE_IDS["bench"], _interval(competition_start)
    )
    first_competitor_id = first_competitor["request"]["id"]
    second_competitor_id = second_competitor["request"]["id"]

    _login(client, "lab_manager")
    queue = client.get("/api/manager/requests")
    assert queue.status_code == 200, queue.text
    competitor_items = {
        item["request"]["id"]: item
        for item in queue.json()["items"]
        if item["request"]["id"] in {first_competitor_id, second_competitor_id}
    }
    assert len(competitor_items) == 2
    assert all(item["eligibility"]["eligible"] for item in competitor_items.values())
    assert all(item["allocation_recommendation"]["recommendation"] for item in competitor_items.values())

    waitlist_reason = "Waitlisted because the overlapping request was ranked first."
    waitlisted = client.post(
        f"/api/requests/{second_competitor_id}/decision",
        json={"outcome": "waitlisted", "reason": waitlist_reason},
    )
    assert waitlisted.status_code == 200, waitlisted.text
    assert waitlisted.json()["request"]["status"] == "WAITLISTED"
    assert waitlist_reason in waitlisted.json()["decision"]["explanation"]

    approved_competitor = client.post(
        f"/api/requests/{first_competitor_id}/decision",
        json={
            "outcome": "approved",
            "reason": "Approved as the competing slot's selected request.",
        },
    )
    assert approved_competitor.status_code == 200, approved_competitor.text

    _login(client, "requester_b")
    b_history = client.get("/api/requests/mine")
    assert b_history.status_code == 200, b_history.text
    stored_waitlist = next(
        item
        for item in b_history.json()["items"]
        if item["request"]["id"] == second_competitor_id
    )
    assert stored_waitlist["request"]["status"] == "WAITLISTED"
    assert waitlist_reason in stored_waitlist["decision"]["explanation"]
    assert stored_waitlist["booking"] is None


def test_missing_training_and_maintenance_hold_are_not_approvable(
    client: TestClient,
) -> None:
    _login(client, "requester_c")
    start = datetime.now(timezone.utc) + timedelta(days=4)
    start = start.replace(second=0, microsecond=0)
    missing_training = _submit_request(
        client,
        RESOURCE_IDS["oscilloscope"],
        _interval(start),
    )
    assert missing_training["request"]["status"] == "INELIGIBLE"
    assert missing_training["eligibility"]["eligible"] is False
    training_blocker = next(
        blocker
        for blocker in missing_training["eligibility"]["blockers"]
        if blocker["code"] == "missing_training"
    )
    assert training_blocker["requirement_codes"] == ["OSCILLOSCOPE_SAFETY"]
    assert training_blocker["next_action"]

    _login(client, "requester_a")
    hold_start = start + timedelta(days=1)
    held = _submit_request(
        client,
        RESOURCE_IDS["maintenance"],
        _interval(hold_start),
    )
    assert held["request"]["status"] == "INELIGIBLE"
    assert held["eligibility"]["eligible"] is False
    assert "maintenance_hold" in {
        blocker["code"] for blocker in held["eligibility"]["blockers"]
    }

    _login(client, "lab_manager")
    approval_attempt = client.post(
        f"/api/requests/{held['request']['id']}/decision",
        json={
            "outcome": "approved",
            "reason": "Attempt to approve a request for a resource on hold.",
        },
    )
    assert approval_attempt.status_code == 409, approval_attempt.text
    assert approval_attempt.json()["error"]["code"] == "invalid_state"

    _login(client, "requester_a")
    history = client.get("/api/requests/mine")
    assert history.status_code == 200, history.text
    held_request = next(
        item
        for item in history.json()["items"]
        if item["request"]["id"] == held["request"]["id"]
    )
    assert held_request["request"]["status"] == "INELIGIBLE"
    assert held_request["booking"] is None
