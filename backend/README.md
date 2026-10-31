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

### Deploying with Supabase and Vercel

The frontend's `frontend/vercel.json` forwards `/api` requests to the configured
Render backend. Configure `DATABASE_URL`, `SECRET_KEY`, and `DEMO_PASSWORD` on
the Render backend service, not on Vercel. Vercel hosts the frontend and does not
select the backend database. Keep database credentials in the hosting
environment-variable settings; never put them in frontend variables or source
control. Rotate any database password that has been shared outside the secret
manager.

The automatic seed runs only for an empty database. Changing `DATABASE_URL` to
an existing Supabase database will not replace its current demo records. To
refresh sample data, back up the database, deploy the current backend, enable
`DEMO_MODE=true` only for this restricted demo deployment, then sign in as the
Institution Admin and use **Administration → Reset seeded demo data**. This
replaces rows marked as demo data and repopulates them from the deployed seed;
it does not reset non-demo records. The action is irreversible for the demo
requests, bookings, training records, and audit history it replaces.

After the reset, `GET /api/public/summary` should return the sample cities and
nonzero resource and organization counts. If it does not, verify that Render
uses the intended Supabase `DATABASE_URL` and that the current backend commit
has finished deploying.

## Resource catalog and dashboards

Authenticated users can browse detailed resource profiles at `GET /api/resources`
and `GET /api/resources/{id}`. Requesters can discover resources across
organizations; lab managers see resources in their own organization and can edit
only resources they own. The catalog supports text, city, area, organization,
category, status, supervision, and training filters; details include readiness
and a per-requirement eligibility checklist. Lab managers can create resources
with `POST /api/resources` and edit only resources they own with
`PATCH /api/resources/{id}`. Supply
`policy_change_reason` when activating an initial policy or editing a resource;
each edit creates a new active policy version and leaves existing Access Contracts
unchanged.

Requester and manager summary views are available at
`GET /api/dashboard/requester` and `GET /api/dashboard/manager`. They include
counts and up to five upcoming bookings, pending requests, open incidents, and
training records expiring within 30 days.

The deterministic seed includes eight fictional institutions in Indian cities,
27 fictional resources, 40 fictional users, 80 training records, 120 recent
historical bookings, pending and waitlisted requests, four incidents, and audit
history. All seeded institutions, people, resources, bookings, training,
incidents, and audit entries are synthetic demo data; none represent real
institutions or live institutional statistics. Access labels are informational:
no payments are processed.

Startup upgrades legacy resource and user columns in SQLite and PostgreSQL
databases before serving API requests.

## Booking assistant

Authenticated requesters and lab managers can use `POST /api/assistant/chat`
for deterministic resource search, requirements/readiness explanations, their
own request outcomes, alternatives, and request drafts. The chat endpoint never
submits a request. A client submits a confirmed draft through `POST /api/requests`
and may set `assistant_draft: true` to add an audit event; this flag does not
change eligibility or allocation.

The rules engine is always available. An optional OpenAI-compatible provider is
enabled only when `AI_API_KEY` is set and `AI_PROVIDER` is `openai` or
`openai-compatible`. `AI_BASE_URL` and `AI_MODEL` may override the API endpoint
and default model (`gpt-4o-mini`). Provider calls have an 8-second timeout and
fall back to rules on errors. Only the user's message and scoped resource
identifiers/catalog metadata are sent; resource descriptions, user records, and
bookings are not sent to the model. Chat is limited to 20 messages per user per
10 minutes. Configure provider variables on Render, never in the browser or
Vercel's public frontend bundle. If no provider is configured, the assistant
uses deterministic matching and guidance.

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
