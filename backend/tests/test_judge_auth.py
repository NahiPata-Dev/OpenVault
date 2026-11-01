import pytest
from sqlalchemy import select

from app.models import AccountProfile, AuditEvent, User
from app.seed import DEMO_USER_IDS
from tests.conftest import login


JUDGE_USER_IDS = {
    "requester": DEMO_USER_IDS["requester_a"],
    "manager": DEMO_USER_IDS["lab_manager"],
    "auditor": DEMO_USER_IDS["judge_auditor"],
}


def enable_judge_login(client):
    client.app.state.judge_login_enabled = True


def test_judge_login_is_disabled_by_default(client, monkeypatch):
    monkeypatch.setenv("JUDGE_LOGIN_ENABLED", "false")
    client.app.state.judge_login_enabled = False

    response = client.post("/api/auth/judge-login", json={"role": "requester"})

    assert response.status_code == 404
    assert client.get("/api/auth/session").status_code == 401


def test_session_advertises_judge_login_only_when_enabled(client):
    client.app.state.judge_login_enabled = True

    response = client.get("/api/auth/session")

    assert response.status_code == 200
    assert response.json() == {
        "user": None,
        "judge_mode": False,
        "judge_login_available": True,
        "available_judge_roles": ["requester", "manager", "auditor"],
    }


@pytest.mark.parametrize(
    ("role", "expected_role"),
    (
        ("requester", "requester"),
        ("manager", "lab_manager"),
        ("auditor", "auditor"),
    ),
)
def test_judge_login_uses_only_fixed_demo_users(client, role, expected_role):
    enable_judge_login(client)
    with client.app.state.session_factory() as session:
        session.add(
            User(
                id="8d907b1c-88c4-48ef-87fd-e37ffb270328",
                display_name="Registered Requester",
                role="requester",
                organization_id="registered-org",
                is_demo=False,
                password_hash="not-used",
            )
        )
        session.commit()

    response = client.post("/api/auth/judge-login", json={"role": role})

    assert response.status_code == 200, response.text
    assert response.json()["user"]["id"] == JUDGE_USER_IDS[role]
    assert response.json()["user"]["role"] == expected_role
    assert response.json()["user"]["is_demo"] is True
    assert "password" not in response.json()

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["judge_mode"] is True
    assert session_response.json()["available_judge_roles"] == [
        "requester",
        "manager",
        "auditor",
    ]
    with client.app.state.session_factory() as session:
        user = session.get(User, JUDGE_USER_IDS[role])
        assert user is not None and user.is_demo
        assert session.get(AccountProfile, user.id) is not None
        assert session.scalar(
            select(AuditEvent.id).where(
                AuditEvent.actor_id == user.id,
                AuditEvent.action == "auth.judge_login",
            )
        )


def test_judge_role_switch_requires_judge_session(client):
    enable_judge_login(client)

    anonymous = client.post("/api/auth/judge-switch", json={"role": "manager"})
    assert anonymous.status_code == 403

    login(client, "requester_a")
    normal_session = client.get("/api/auth/session")
    assert normal_session.status_code == 200
    assert normal_session.json()["judge_mode"] is False
    denied = client.post("/api/auth/judge-switch", json={"role": "auditor"})
    assert denied.status_code == 403

    client.post("/api/auth/logout")
    client.post("/api/auth/judge-login", json={"role": "requester"})
    switched = client.post("/api/auth/judge-switch", json={"role": "auditor"})
    assert switched.status_code == 200, switched.text
    assert switched.json()["user"]["id"] == JUDGE_USER_IDS["auditor"]
    assert client.get("/api/auth/session").json()["judge_mode"] is True
    with client.app.state.session_factory() as session:
        assert session.scalar(
            select(AuditEvent.id).where(
                AuditEvent.actor_id == JUDGE_USER_IDS["auditor"],
                AuditEvent.action == "auth.judge_switch",
            )
        )


@pytest.mark.parametrize("role", ("requester", "manager", "auditor"))
def test_judge_session_cannot_reset_demo_data(client, role):
    enable_judge_login(client)
    assert client.post("/api/auth/judge-login", json={"role": role}).status_code == 200

    response = client.post(
        "/api/admin/demo-reset",
        json={"confirmation": "RESET_DEMO_DATA"},
    )

    assert response.status_code == 403


def test_judge_login_rate_limit_is_30_calls_per_ten_minutes(client):
    enable_judge_login(client)

    for _ in range(30):
        response = client.post("/api/auth/judge-login", json={"role": "requester"})
        assert response.status_code == 200, response.text

    limited = client.post("/api/auth/judge-login", json={"role": "requester"})

    assert limited.status_code == 429
    with client.app.state.session_factory() as session:
        assert session.scalar(
            select(AuditEvent.id)
            .where(
                AuditEvent.action == "auth.judge_login",
                AuditEvent.actor_id == JUDGE_USER_IDS["requester"],
            )
            .limit(1)
        )
        assert len(
            session.scalars(
                select(AuditEvent).where(AuditEvent.action == "auth.judge_login")
            ).all()
        ) == 30
