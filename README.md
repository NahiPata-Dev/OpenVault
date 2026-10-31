# OpenVault

OpenVault is a CodeVerse India prototype for discovering shared institutional
resources, checking access requirements, submitting booking requests, and
recording a human manager's decision.

## What is included

- A React, TypeScript, Vite, and Tailwind frontend in `frontend/`.
- A FastAPI backend in `backend/`; it owns authorization, organization scope,
  eligibility checks, request state transitions, and manager decisions.
- SQLite for local development. PostgreSQL can be selected for deployment with
  `DATABASE_URL`.
- A deterministic demo seed with eight fictional institutions in real Indian
  cities: two in Hyderabad and one each in Bengaluru, Chennai, Pune, Mumbai,
  Delhi NCR, and Kolkata. The areas are real; every institution and person is
  fictional and visibly marked as sample data. The seed contains 27 resources,
  40 fictional users, 80 training records, 120 historical bookings, pending
  and waitlisted requests, incidents, and audit events.
- A public, read-only city summary for the sample catalog. Authenticated catalog
  filters include city, area, organization, category, and text.

Seeded sample counts and statistics are illustrative demo data, not live
institutional data. Access models are display text only; no payments are
processed.

## Run locally

In one PowerShell terminal, follow the backend setup and start instructions in
[`backend/README.md`](./backend/README.md). The local API listens on
`http://127.0.0.1:8000`.

In another terminal:

```powershell
Set-Location .\frontend
npm install
npm run dev
```

Open the frontend URL printed by Vite (by default,
`http://127.0.0.1:5173`). The development server proxies `/api` requests to
`http://127.0.0.1:8000`. Configure `VITE_API_URL` if the API uses another
origin. The app uses the backend API; it does not use a local mock catalog.

The demo accounts and shared demo password are documented in
[`backend/README.md`](./backend/README.md). Use
[`docs/MANUAL_TEST.md`](./docs/MANUAL_TEST.md) for the manual sample journeys.

## Build and tests

Build the frontend from its package directory:

```powershell
Set-Location .\frontend
npm run build
npm test
```

Run backend tests from `backend/` with the project dependencies installed:

```powershell
Set-Location .\backend
$env:SECRET_KEY = "test-session-secret-key-that-is-long-enough"
$env:DEMO_PASSWORD = "test-demo-password"
python -m pytest -q
```

Backend tests use isolated temporary SQLite databases and do not reset the local
demo database.

## Booking assistant

Requesters and lab managers can ask the booking assistant to find resources,
explain requirements, check eligibility, review their own request outcomes, or
prepare a request draft. The deterministic rules engine always provides the
core behavior. An optional OpenAI-compatible model can interpret the message
and phrase a response when both `AI_API_KEY` and a supported `AI_PROVIDER` are
configured; otherwise the assistant uses rules.

The assistant only prepares draft data. It never submits, approves, or
waitlists a request and cannot bypass eligibility or other rules. A requester
must explicitly confirm through the normal request endpoint; the backend
performs the authoritative eligibility check and records the request for a
human manager's decision. See the backend README for provider configuration and
data boundaries.

## Limitations

- No real institutional identity, student information, training, calendar,
  facilities, or resource-management system is integrated.
- No payments, deposits, or fines are processed.
- The assistant cannot approve requests, make allocation decisions, or override
  eligibility, training, safety, or booking rules.
- The optional model layer is inactive when no API key is configured (or when
  no supported provider is configured); rules-based behavior remains available.
- Seeded organizations, users, requests, bookings, training, incidents, and
  metrics are synthetic and are not institutional records or live statistics.
