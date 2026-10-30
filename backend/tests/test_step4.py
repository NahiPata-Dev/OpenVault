from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.models import AuditEvent, Booking, HandoverReport, Incident, Resource, ResourceRequest
from app.seed import DEMO_USER_IDS, RESOURCE_IDS
from tests.conftest import login

CHECKLIST = "northstar-condition-v1"
GOOD = {
    "physical_condition": "ok",
    "accessories_complete": "yes",
    "functional_test": "works",
    "notes": None,
}


def _new_booking(client, requester_key="requester_a", days=0, minutes=5):
    start = datetime.now(timezone.utc) + timedelta(days=days, minutes=minutes)
    start = start.replace(second=0, microsecond=0)
    end = start + timedelta(hours=1)
    request_id = str(uuid4())
    with client.app.state.session_factory() as session:
        session.add(
            ResourceRequest(
                id=request_id,
                requester_id=DEMO_USER_IDS[requester_key],
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
    login(client, "lab_manager")
    approved = client.post(
        f"/api/requests/{request_id}/decision",
        json={"outcome": "approved", "reason": "Approved for lifecycle test."},
    )
    assert approved.status_code == 200, approved.text
    login(client, requester_key)
    return approved.json()["booking"]["id"]


def _handover(condition=GOOD, evidence=None):
    return {
        "checklist_version": CHECKLIST,
        "condition": condition,
        "evidence_references": evidence or [],
    }


def test_checkin_checkout_and_duplicate_submissions_rejected(client):
    booking_id = _new_booking(client)
    checkin = client.post(
        f"/api/bookings/{booking_id}/check-in", json=_handover()
    )
    assert checkin.status_code == 200, checkin.text
    assert checkin.json()["booking"]["status"] == "CHECKED_IN"
    duplicate_in = client.post(
        f"/api/bookings/{booking_id}/check-in", json=_handover()
    )
    assert duplicate_in.status_code == 409
    assert duplicate_in.json()["error"]["code"] == "invalid_state"

    checkout = client.post(
        f"/api/bookings/{booking_id}/check-out",
        json=_handover(evidence=[{"file_name": "return.txt", "note": "Condition checked."}]),
    )
    assert checkout.status_code == 200, checkout.text
    assert checkout.json()["booking"]["status"] == "CLOSED"
    duplicate_out = client.post(
        f"/api/bookings/{booking_id}/check-out", json=_handover()
    )
    assert duplicate_out.status_code == 409
    assert duplicate_out.json()["error"]["code"] == "invalid_state"


def test_checkout_before_checkin_is_rejected(client):
    booking_id = _new_booking(client)
    response = client.post(
        f"/api/bookings/{booking_id}/check-out", json=_handover()
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_out_of_window_checkin_is_rejected(client):
    booking_id = _new_booking(client, days=0, minutes=120)
    response = client.post(
        f"/api/bookings/{booking_id}/check-in", json=_handover()
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_wrong_user_cannot_check_in(client):
    booking_id = _new_booking(client, requester_key="requester_a")
    login(client, "requester_b")
    response = client.post(
        f"/api/bookings/{booking_id}/check-in", json=_handover()
    )
    assert response.status_code == 403


def test_discrepancy_creates_reviewable_incident_without_blame(client):
    booking_id = _new_booking(client)
    checked_in = client.post(
        f"/api/bookings/{booking_id}/check-in", json=_handover()
    )
    assert checked_in.status_code == 200, checked_in.text
    damaged = {
        "physical_condition": "damaged",
        "accessories_complete": "no",
        "functional_test": "issue",
        "notes": "Synthetic return discrepancy.",
    }
    checked_out = client.post(
        f"/api/bookings/{booking_id}/check-out", json=_handover(damaged)
    )
    assert checked_out.status_code == 200, checked_out.text
    body = checked_out.json()
    assert body["booking"]["status"] == "INCIDENT_REVIEW"
    assert body["incident"]["category"] == "other"
    assert "fault" not in body["incident"]
    assert "blame" not in body["incident"]

    denied = client.post(
        f"/api/incidents/{body['incident']['id']}/resolve",
        json={"outcome": "resolved", "rationale": "Requester must not resolve."},
    )
    assert denied.status_code == 403


def test_incident_review_resolution_and_critical_audit_events(client):
    booking_id = _new_booking(client)
    assert client.post(
        f"/api/bookings/{booking_id}/check-in", json=_handover()
    ).status_code == 200
    damaged = {**GOOD, "physical_condition": "minor_wear"}
    result = client.post(
        f"/api/bookings/{booking_id}/check-out", json=_handover(damaged)
    )
    assert result.status_code == 200, result.text
    incident_id = result.json()["incident"]["id"]

    login(client, "lab_manager")
    review = client.post(
        f"/api/incidents/{incident_id}/review",
        json={"status": "under_review", "reason": "Reviewing the reported condition."},
    )
    assert review.status_code == 200, review.text
    resolved = client.post(
        f"/api/incidents/{incident_id}/resolve",
        json={"outcome": "resolved", "rationale": "Checklist discrepancy reviewed."},
    )
    assert resolved.status_code == 200, resolved.text

    with client.app.state.session_factory() as session:
        booking = session.get(Booking, booking_id)
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.entity_id == booking_id)
        ).all()
        actions = {event.action for event in events}
        assert {"booking.checked_in", "booking.checked_out", "booking.incident_review_opened", "booking.closed_after_review"} <= actions
        request_events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.entity_id == booking.request_id
            )
        ).all()
        assert {
            "request.approved",
        } <= {event.action for event in request_events}
        incident_events = session.scalars(
            select(AuditEvent).where(AuditEvent.entity_id == incident_id)
        ).all()
        assert {event.action for event in incident_events} >= {
            "incident.opened",
            "incident.review_started",
            "incident.resolved",
        }


def test_maintenance_hold_blocks_checkin(client):
    booking_id = _new_booking(client)
    with client.app.state.session_factory() as session:
        booking = session.get(Booking, booking_id)
        resource = session.get(Resource, booking.request.resource_id)
        resource.status = "maintenance_hold"
        resource.hold_review_date = datetime.now(timezone.utc).date()
        session.commit()
    response = client.post(
        f"/api/bookings/{booking_id}/check-in", json=_handover()
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ineligible"


def test_idempotent_checkin_retry_returns_saved_report(client):
    booking_id = _new_booking(client)
    response = client.post(
        f"/api/bookings/{booking_id}/check-in",
        json=_handover(),
        headers={"Idempotency-Key": "checkin-key-1"},
    )
    assert response.status_code == 200, response.text
    repeated = client.post(
        f"/api/bookings/{booking_id}/check-in",
        json=_handover(),
        headers={"Idempotency-Key": "checkin-key-1"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["handover_report"]["id"] == response.json()["handover_report"]["id"]
