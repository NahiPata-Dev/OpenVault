from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.models import AccountProfile


class FakeOAuthClient:
    def __init__(self, claims):
        self.claims = claims

    async def authorize_redirect(self, request, redirect_uri):
        assert redirect_uri == "https://api.example.test/api/auth/google/callback"
        return RedirectResponse("https://provider.example.test/authorize", status_code=302)

    async def authorize_access_token(self, request):
        return {"userinfo": self.claims}


class FakeOAuth:
    def __init__(self, client):
        self.client = client

    def create_client(self, provider):
        return self.client if provider == "google" else None


def _register(client):
    return client.post(
        "/api/auth/register",
        json={
            "full_name": "OAuth User",
            "email": "oauth-user@example.test",
            "password": "valid-password-83",
            "organization_name": "Example University",
        },
    )


def _configure_google(client, claims):
    client.app.state.oauth = FakeOAuth(FakeOAuthClient(claims))
    client.app.state.oauth_redirect_base_url = "https://api.example.test"
    client.app.state.frontend_base_url = "https://openvault.example.test"


def test_oauth_providers_are_disabled_without_configuration(client):
    response = client.get("/api/auth/providers")

    assert response.status_code == 200
    assert response.json() == {"providers": {"google": False, "linkedin": False}}
    unavailable = client.get("/api/auth/google/start")
    assert unavailable.status_code == 503


def test_oauth_login_requires_verified_email_and_uses_safe_next_path(client):
    registered = _register(client)
    assert registered.status_code == 201, registered.text
    _configure_google(
        client,
        {"email": "oauth-user@example.test", "email_verified": True},
    )

    started = client.get(
        "/api/auth/google/start",
        params={"next": "//attacker.example"},
        follow_redirects=False,
    )
    assert started.status_code == 302
    assert started.headers["location"] == "https://provider.example.test/authorize"

    callback = client.get(
        "/api/auth/google/callback?code=example&state=state",
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert callback.headers["location"] == "https://openvault.example.test/resources"
    assert client.get("/api/auth/session").json()["user"]["id"] == registered.json()["user"]["id"]
    with client.app.state.session_factory() as session:
        profile = session.scalar(
            select(AccountProfile).where(AccountProfile.email == "oauth-user@example.test")
        )
        assert profile.email_verified is True


def test_oauth_login_rejects_unverified_email(client):
    assert _register(client).status_code == 201
    _configure_google(
        client,
        {"email": "oauth-user@example.test", "email_verified": False},
    )
    client.get("/api/auth/google/start", follow_redirects=False)

    callback = client.get(
        "/api/auth/google/callback?code=example&state=state",
        follow_redirects=False,
    )

    assert callback.status_code == 303
    assert "oauth_error=unverified_email" in callback.headers["location"]
    assert client.get("/api/auth/session").status_code == 401