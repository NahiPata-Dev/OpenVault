# OpenVault Backend

FastAPI modular monolith for the Northstar Engineering Lab (DEMO). SQLite is the
local default; set `DATABASE_URL` to a PostgreSQL URL when deployed. The API
creates tables with SQLAlchemy `create_all`; the seed command is deterministic
and does not use Alembic.

## Setup and run (PowerShell)

From the repository root:

```powershell
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

$env:DATABASE_URL = "sqlite:///./openvault.db"
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:DEMO_PASSWORD = "northstar-demo"
$env:DEMO_MODE = "true"

python -m app.seed
python -m uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive API documentation
is at `http://127.0.0.1:8000/docs`. Keep the generated `SECRET_KEY` in the
server environment and use the same value while the server is running. Set
`COOKIE_SECURE=true` behind HTTPS. Set `ALLOWED_ORIGINS` to a comma-separated
list of exact frontend origins (for example `https://openvault.example.com`).
`DEMO_MODE=true` enables the restricted
demo-reset endpoint and should not be enabled in a production environment.

Google and LinkedIn sign-in are optional OIDC providers. Configure the matching
`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` or `LINKEDIN_CLIENT_ID` /
`LINKEDIN_CLIENT_SECRET`, set `OAUTH_REDIRECT_BASE_URL` to the public API origin
and `FRONTEND_BASE_URL` to the frontend origin, and register
`{OAUTH_REDIRECT_BASE_URL}/api/auth/{provider}/callback` with each provider.
Provider sign-in accepts only verified emails already registered in OpenVault;
new users should create an account first. Unconfigured providers are not shown.

AI chat uses a server-side OpenAI-compatible provider. Set `OPENROUTER_API_KEY`
for OpenRouter (default model `openai/gpt-4o-mini`), or set `AI_API_KEY` and
`AI_BASE_URL` / `AI_MODEL` for another compatible provider. Optional OpenRouter
settings are `OPENROUTER_MODEL`, `OPENROUTER_SITE_URL`, and `OPENROUTER_APP_NAME`.
Store the key only in the backend environment or deployment secret manager; do
not use a `VITE_` variable or commit it. The recent chat, profile intended-use
text, and relevant same-organization resource details are sent to that provider
to generate replies. AI chat stays disabled until a provider is configured.
Configure these values in the backend process environment or a deployment secret
manager. A local `.env` file is git-ignored but is not loaded automatically by
the API process.

`DATABASE_URL` defaults to `sqlite:///./openvault.db`. At startup, the app
creates the schema and seeds the deterministic DEMO records only when the
database has no users. The seed script follows the same rule and leaves a
database containing any user unchanged; use the restricted reset endpoint to
reset only demo rows.

## Resource catalog and dashboards

Authenticated users can browse detailed resource profiles at `GET /api/resources`
and `GET /api/resources/{id}`. The catalog supports text, category, status,
supervision, and training filters; details include readiness and a per-requirement
eligibility checklist. Lab managers can create resources with `POST /api/resources`
and edit only resources they own with `PATCH /api/resources/{id}`. Supply
`policy_change_reason` when activating an initial policy or editing a resource;
each edit creates a new active policy version and leaves existing Access Contracts
unchanged.

Requester and manager summary views are available at
`GET /api/dashboard/requester` and `GET /api/dashboard/manager`. They include
counts and up to five upcoming bookings, pending requests, open incidents, and
training records expiring within 30 days.

The deterministic demo seed includes six fictional resources marked as sample
data, historical booking and training records, competing requests, a waitlist
explanation, and audit history. Startup upgrades the legacy resource table in
SQLite and PostgreSQL databases before serving API requests.

## Demo login

The visible shared demo password is **`northstar-demo`**. The stored account
passwords are hashed; authentication uses a signed HttpOnly session cookie.

| Demo account button | Role |
|---|---|
| Requester A | requester |
| Requester B | requester |
| Requester C | requester |
| Lab Manager | lab_manager |
| Institution Admin | institution_admin |
| Judge Auditor | auditor |

Use the account list at `GET /api/auth/demo-accounts` to populate the login
buttons. The auditor and institution administrator are separate accounts.

## Tests

In the backend directory, with the virtual environment active:

```powershell
$env:SECRET_KEY = "test-session-secret-key-that-is-long-enough"
$env:DEMO_PASSWORD = "test-demo-password"
python -m pytest -q
```

The pytest fixtures create isolated temporary SQLite databases and seed them
with the test password. They do not use or reset `openvault.db`.
