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

`DATABASE_URL` defaults to `sqlite:///./openvault.db`. At startup, the app
creates the schema and seeds the deterministic DEMO records only when the
database has no users. The seed script follows the same rule and leaves a
database containing any user unchanged; use the restricted reset endpoint to
reset only demo rows.

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
