from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, build_engine, build_session_factory
from app.main import create_app
from app.models import AuditEvent, ResourceRequest, User
from app.seed import DEMO_USER_IDS, RESOURCE_IDS, seed_database
from tests.conftest import login


def _request_body(resource_id: str) -> dict:
    start = (datetime.now(timezone.utc) + timedelta(days=4)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    return {
        "resource_id": resource_id,
        "purpose": "project",
        "start_at": start.isoformat(),
        "end_at": (start + timedelta(hours=1)).isoformat(),
    }


def test_requester_and_anonymous_are_denied_manager_endpoints(client, requester_login):
    protected = [
        (
            "POST",
            "/api/resources",
            {
                "name": "Denied Resource",
                "category": "equipment",
                "location": "Lab",
                "weekly_operating_hours": [],
            },
        ),
        (
            "GET",
            "/api/manager/requests",
            None,
        ),
        (
            "POST",
            f"/api/resources/{RESOURCE_IDS['camera']}/policy-drafts",
            {
                "structured_requirements": {
                    "training_codes": [],
                    "supervisor_required": False,
                    "supervised_windows": [],
                },
                "allowed_uses": ["project"],
                "priority_policy": {},
            },
        ),
        (
            "POST",
            "/api/training-records",
            {
                "user_id": DEMO_USER_IDS["requester_a"],
                "requirement_code": "TEST",
                "status": "valid",
                "valid_from": datetime.now(timezone.utc).isoformat(),
                "valid_to": None,
            },
        ),
    ]
    for method, path, body in protected:
        response = requester_login.request(method, path, json=body)
        assert response.status_code == 403, (path, response.text)
        assert response.json()["error"]["code"] == "forbidden"

    anonymous = TestClient(client.app)
    for method, path, body in protected:
        response = anonymous.request(method, path, json=body)
        assert response.status_code == 401, (path, response.text)
        assert response.json()["error"]["code"] == "forbidden"
    anonymous.close()


def test_requester_c_submission_persists_missing_training_blocker(requester_login):
    login(requester_login, "requester_c")
    response = requester_login.post(
        "/api/requests",
        json=_request_body(RESOURCE_IDS["oscilloscope"]),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["request"]["status"] == "INELIGIBLE"
    blocker = next(item for item in body["eligibility"]["blockers"] if item["code"] == "missing_training")
    assert blocker["requirement_codes"] == ["OSCILLOSCOPE_SAFETY"]


def test_audit_history_has_no_update_or_delete_api(client, requester_login):
    start = _request_body(RESOURCE_IDS["camera"])
    response = requester_login.post("/api/requests", json=start)
    assert response.status_code == 201, response.text
    event_id = None
    with client.app.state.session_factory() as session:
        event = session.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "request",
                AuditEvent.entity_id == response.json()["request"]["id"],
            )
            .order_by(AuditEvent.timestamp)
            .limit(1)
        )
        event_id = event.id
    for method in ("PATCH", "DELETE"):
        result = client.request(method, f"/api/audit/{event_id}")
        assert result.status_code == 404
        assert result.json()["error"]["code"] == "not_found"


def test_startup_seeds_empty_database_and_never_reseeds_existing_user(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "northstar-demo")
    empty_url = f"sqlite:///{tmp_path / 'empty.sqlite'}"
    empty_app = create_app(
        database_url=empty_url,
        secret_key="startup-seed-test-secret",
        initialize_database=True,
    )
    with TestClient(empty_app):
        with empty_app.state.session_factory() as session:
            assert session.scalar(select(User.id)) is not None
            assert len(session.scalars(select(User)).all()) == 6

    existing_url = f"sqlite:///{tmp_path / 'existing.sqlite'}"
    engine = build_engine(existing_url)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory() as session:
        session.add(
            User(
                id=str(uuid4()),
                display_name="Existing Non-demo User",
                role="requester",
                organization_id="northstar-engineering-lab-demo",
                is_demo=False,
                password_hash="already-stored-hash",
            )
        )
        session.commit()
    existing_app = create_app(
        database_url=existing_url,
        secret_key="startup-seed-test-secret",
        initialize_database=True,
    )
    with TestClient(existing_app):
        with existing_app.state.session_factory() as session:
            assert len(session.scalars(select(User)).all()) == 1
            assert session.scalar(select(User.id).where(User.id == DEMO_USER_IDS["requester_a"])) is None
    engine.dispose()


def test_startup_does_not_seed_database_with_non_user_data(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'partial-data.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory() as session:
        session.add(
            AuditEvent(
                id=str(uuid4()),
                actor_id=None,
                entity_type="system",
                entity_id=str(uuid4()),
                action="existing.data",
                timestamp=datetime.now(timezone.utc),
                is_demo=False,
            )
        )
        session.commit()
    app = create_app(
        database_url=database_url,
        secret_key="partial-data-test-secret",
        initialize_database=True,
    )
    with TestClient(app):
        with app.state.session_factory() as session:
            assert session.scalar(select(User.id)) is None
            assert len(session.scalars(select(AuditEvent)).all()) == 1
    engine.dispose()


def test_health_cors_and_secure_cookie_environment(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'secure-cookie.sqlite'}"
    monkeypatch.setenv("DEMO_PASSWORD", "northstar-demo")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://demo.openvault.example")
    app = create_app(
        database_url=database_url,
        secret_key="secure-cookie-test-secret",
        initialize_database=True,
    )
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        preflight = client.options(
            "/api/auth/demo-accounts",
            headers={
                "Origin": "https://demo.openvault.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "https://demo.openvault.example"
        account = next(
            item
            for item in client.get("/api/auth/demo-accounts").json()["accounts"]
            if item["display_name"] == "Requester A"
        )
        response = client.post(
            "/api/auth/demo-login",
            json={"account_id": account["id"], "password": "northstar-demo"},
        )
        cookie = response.headers["set-cookie"].casefold()
        assert "httponly" in cookie
        assert "samesite=lax" in cookie
        assert "secure" in cookie
