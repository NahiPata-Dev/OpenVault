from datetime import date

from app.models import Resource
from app.seed import DEMO_USER_IDS, RESOURCE_IDS


def test_resource_create_and_read_persists(client, manager_login):
    payload = {
        "name": "Test Electronics Bench",
        "category": "electronics",
        "capability_tags": ["soldering", "measurement"],
        "location": "Northstar Lab - Test Bay",
        "status": "active",
        "weekly_operating_hours": [
            {"weekday": 1, "start": "09:00", "end": "17:00"}
        ],
        "max_duration_minutes": 120,
        "exclusive_booking": True,
    }

    created = manager_login.post("/api/resources", json=payload)

    assert created.status_code == 201, created.text
    body = created.json()
    resource_id = body["resource"]["id"]
    assert body["resource"]["name"] == payload["name"]
    assert {item["code"] for item in body["readiness"]["blockers"]} == {
        "policy_missing"
    }

    fetched = manager_login.get(f"/api/resources/{resource_id}")
    assert fetched.status_code == 200
    assert fetched.json()["resource"]["id"] == resource_id
    assert fetched.json()["resource"]["weekly_operating_hours"] == payload[
        "weekly_operating_hours"
    ]

    listed = manager_login.get("/api/resources", params={"query": "Test Electronics"})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [resource_id]


def test_requester_gets_403_on_resource_create(client, requester_login):
    response = requester_login.post("/api/resources", json=resource_payload())

    assert response.status_code == 403
    assert_error_format(response.json(), "forbidden")


def test_unauthenticated_gets_401_on_resource_create(client):
    response = client.post("/api/resources", json=resource_payload())

    assert response.status_code == 401
    assert_error_format(response.json(), "forbidden")


def test_framework_validation_error_uses_contract_shape(manager_login):
    response = manager_login.post(
        "/api/resources",
        json={**resource_payload(), "name": ""},
    )

    assert response.status_code == 422
    assert_error_format(response.json(), "validation_error")


def test_demo_login_sets_signed_httponly_session_cookie(client):
    response = client.post(
        "/api/auth/demo-login",
        json={
            "account_id": DEMO_USER_IDS["requester_a"],
            "password": "test-demo-password",
        },
    )

    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "openvault_session=" in cookie
    assert "httponly" in cookie.casefold()
    assert client.get("/api/auth/session").json()["user"]["role"] == "requester"


def test_seed_contains_contract_demo_entities(client):
    with client.app.state.session_factory() as session:
        assert session.get(Resource, RESOURCE_IDS["maintenance"]).status == "maintenance_hold"
        assert session.get(Resource, RESOURCE_IDS["maintenance"]).hold_review_date <= date.today()


def resource_payload() -> dict:
    return {
        "name": "Test Resource",
        "category": "equipment",
        "capability_tags": [],
        "location": "Northstar",
        "weekly_operating_hours": [],
    }


def assert_error_format(body: dict, expected_code: str) -> None:
    assert set(body) == {"error"}
    error = body["error"]
    assert set(error) == {"code", "message", "details", "request_id"}
    assert error["code"] == expected_code
    assert isinstance(error["message"], str)
    assert isinstance(error["details"], list)
    assert isinstance(error["request_id"], str)
