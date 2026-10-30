import base64
import json

from itsdangerous import TimestampSigner
from sqlalchemy import select

from app.models import AuditEvent, OwnerApplication, User
from app.seed import DEMO_USER_IDS


def register(client, **overrides):
    payload = {
        "full_name": "Avery Student",
        "email": "avery@example.test",
        "password": "secure-passphrase-47",
        "organization_name": "Example University",
        "intended_use": "Borrow project equipment",
    }
    payload.update(overrides)
    return client.post("/api/auth/register", json=payload)


def test_registration_rejects_client_supplied_role(client):
    response = register(client, role="institution_admin")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_duplicate_email_is_case_insensitive(client):
    assert register(client).status_code == 201

    duplicate = register(client, email="  AVERY@EXAMPLE.TEST ")

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"


def test_registration_rejects_numeric_password(client):
    response = register(client, password="1234567890")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_login_rate_limit_is_per_account_and_ip(client):
    assert register(client).status_code == 201
    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={"email": "avery@example.test", "password": "wrong-password"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "Invalid email or password."

    limited = client.post(
        "/api/auth/login",
        json={"email": "avery@example.test", "password": "wrong-password"},
    )

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"


def test_login_rate_limit_also_applies_across_accounts_per_ip(client):
    for index in range(5):
        response = client.post(
            "/api/auth/login",
            json={
                "email": f"unknown-{index}@example.test",
                "password": "wrong-password",
            },
        )
        assert response.status_code == 401

    limited = client.post(
        "/api/auth/login",
        json={"email": "another-unknown@example.test", "password": "wrong-password"},
    )

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"


def test_wrong_password_uses_generic_credentials_message(client):
    assert register(client).status_code == 201

    wrong_existing = client.post(
        "/api/auth/login",
        json={"email": "avery@example.test", "password": "not-the-password"},
    )
    unknown_email = client.post(
        "/api/auth/login",
        json={"email": "missing@example.test", "password": "not-the-password"},
    )

    assert wrong_existing.status_code == unknown_email.status_code == 401
    assert wrong_existing.json()["error"]["message"] == "Invalid email or password."
    assert unknown_email.json()["error"]["message"] == "Invalid email or password."


def test_change_password_invalidates_old_password(client):
    assert register(client).status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"email": "avery@example.test", "password": "secure-passphrase-47"},
    )
    assert login.status_code == 200

    changed = client.post(
        "/api/me/change-password",
        json={
            "current_password": "secure-passphrase-47",
            "new_password": "different-passphrase-83",
        },
    )
    assert changed.status_code == 200
    assert client.get("/api/auth/session").status_code == 200

    old_password = client.post(
        "/api/auth/login",
        json={"email": "avery@example.test", "password": "secure-passphrase-47"},
    )
    new_password = client.post(
        "/api/auth/login",
        json={"email": "avery@example.test", "password": "different-passphrase-83"},
    )

    assert old_password.status_code == 401
    assert new_password.status_code == 200


def test_requester_cannot_decide_owner_application(client):
    assert register(client).status_code == 201
    assert client.post(
        "/api/auth/login",
        json={"email": "avery@example.test", "password": "secure-passphrase-47"},
    ).status_code == 200
    application = client.post(
        "/api/owner-applications",
        json={
            "organization": "Example University",
            "role_in_organization": "Lab coordinator",
            "reason": "I coordinate equipment access.",
            "resources_to_list": "Electronics benches",
        },
    )
    assert application.status_code == 201
    own_application = client.get("/api/me/owner-application")
    assert own_application.status_code == 200
    assert client.get("/api/admin/users").status_code == 403
    assert own_application.json()["application"]["id"] == application.json()["id"]

    response = client.post(
        f"/api/admin/owner-applications/{application.json()['id']}/decision",
        json={"outcome": "approved", "reason": "Not authorized"},
    )

    assert response.status_code == 403


def test_approval_changes_role_and_writes_audit_event(client):
    registered = register(client)
    assert registered.status_code == 201
    applicant_id = registered.json()["user"]["id"]
    assert client.post(
        "/api/auth/login",
        json={"email": "avery@example.test", "password": "secure-passphrase-47"},
    ).status_code == 200
    application = client.post(
        "/api/owner-applications",
        json={
            "organization": "Example University",
            "role_in_organization": "Lab coordinator",
            "reason": "I coordinate equipment access.",
            "resources_to_list": "Electronics benches",
        },
    ).json()
    own_application = client.get("/api/me/owner-application")
    assert own_application.status_code == 200
    admin_login = client.post(
        "/api/auth/demo-login",
        json={
            "account_id": DEMO_USER_IDS["institution_admin"],
            "password": "test-demo-password",
        },
    )
    assert admin_login.status_code == 200
    applications = client.get("/api/admin/owner-applications")
    assert applications.status_code == 200
    assert application["id"] in {row["id"] for row in applications.json()}
    admin_id = DEMO_USER_IDS["institution_admin"]

    decision = client.post(
        f"/api/admin/owner-applications/{application['id']}/decision",
        json={"outcome": "approved", "reason": "Organization verified."},
    )

    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "approved"
    admin_users = client.get("/api/admin/users")
    assert admin_users.status_code == 200
    approved_account = next(
        row for row in admin_users.json() if row["id"] == applicant_id
    )
    assert approved_account["role"] == "lab_manager"
    assert approved_account["status"] == "active"
    with client.app.state.session_factory() as session:
        applicant = session.get(User, applicant_id)
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_type == "owner_application",
                AuditEvent.entity_id == application["id"],
                AuditEvent.action == "owner_application.approved",
            )
        )
        stored_application = session.get(OwnerApplication, application["id"])
        assert applicant.role == "lab_manager"
        assert applicant.organization_id.startswith("org-")
        assert stored_application.decision_reason == "Organization verified."
        assert event is not None
        assert event.actor_id == admin_id
        actions = set(
            session.scalars(
                select(AuditEvent.action).where(
                    AuditEvent.entity_type.in_(
                        ("owner_application", "owner_application_query")
                    ),
                    AuditEvent.entity_id.in_((application["id"], applicant_id, admin_id)),
                )
            ).all()
        )
        assert {
            "owner_application.submitted",
            "owner_application.viewed",
            "owner_applications.listed",
            "owner_application.approved",
        } <= actions


def test_session_expiry_rejects_old_signed_cookie(client):
    user_id = DEMO_USER_IDS["requester_a"]

    class ExpiredSigner(TimestampSigner):
        def get_timestamp(self):
            return super().get_timestamp() - 13 * 60 * 60

    serialized = base64.b64encode(
        json.dumps({"user_id": user_id, "auth_version": 0}).encode("utf-8")
    )
    cookie = ExpiredSigner("test-session-secret-key-that-is-long-enough").sign(
        serialized
    ).decode("ascii")
    client.cookies.set("openvault_session", cookie)

    response = client.get("/api/auth/session")

    assert response.status_code == 401


def test_seeded_demo_account_can_read_profile(client):
    response = client.post(
        "/api/auth/demo-login",
        json={
            "account_id": DEMO_USER_IDS["requester_a"],
            "password": "test-demo-password",
        },
    )
    assert response.status_code == 200

    profile = client.get("/api/me")

    assert profile.status_code == 200
    assert profile.json()["role"] == "requester"
    assert profile.json()["email"] is None


def test_profile_cannot_change_role(client):
    assert register(client).status_code == 201
    assert client.post(
        "/api/auth/login",
        json={"email": "avery@example.test", "password": "secure-passphrase-47"},
    ).status_code == 200

    response = client.patch("/api/me", json={"role": "lab_manager"})

    assert response.status_code == 422
    email_verification = client.patch("/api/me", json={"email_verified": True})
    assert email_verification.status_code == 422
    organization_scope = client.patch(
        "/api/me", json={"organization_id": "untrusted-scope"}
    )
    assert organization_scope.status_code == 422
    with client.app.state.session_factory() as session:
        user = session.scalar(
            select(User).where(User.role == "requester", User.is_demo.is_(False))
        )
        original_scope = user.organization_id
    profile_update = client.patch("/api/me", json={"organization_name": "Renamed"})
    assert profile_update.status_code == 200
    with client.app.state.session_factory() as session:
        user = session.get(User, user.id)
        assert user.organization_id == original_scope
    profile = client.get("/api/me")
    assert profile.status_code == 200
    assert profile.json()["role"] == "requester"


def test_security_headers_and_request_body_limit(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "https://cdn.jsdelivr.net" in docs.headers["content-security-policy"]

    oversized = client.post(
        "/api/auth/register",
        content=b"x" * (1_048_577),
        headers={"content-type": "application/json"},
    )
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "request_too_large"
    assert oversized.headers["x-content-type-options"] == "nosniff"
