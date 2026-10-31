# OpenVault Project Document

## Project overview

OpenVault is a CodeVerse India prototype for finding shared resources, reviewing
their requirements, submitting access requests, and recording decisions made by
authorized human managers. It demonstrates a resource-access workflow; it is
not connected to a real institution.

## Application structure

- `frontend/` contains the React, TypeScript, and Vite browser application.
  Authenticated pages use the backend API for catalog, assistant, request, and
  management data.
- `backend/` contains the FastAPI application and SQLAlchemy data model. The
  backend is authoritative for session identity, organization scope,
  eligibility, request state transitions, and manager decisions.
- Local development uses SQLite. Deployment can configure PostgreSQL through
  `DATABASE_URL`; schema initialization uses SQLAlchemy `create_all`.

The backend README documents setup, environment variables, and demo accounts.
The manual walkthrough is in [`MANUAL_TEST.md`](./MANUAL_TEST.md).

## Synthetic multi-city catalog

The deterministic seed contains eight fictional institutions, all marked as
sample data and named with a `(Sample)` suffix. They are placed in real Indian
cities and areas: two institutions in Hyderabad (Gachibowli and Uppal), and one
each in Bengaluru (Electronic City), Chennai (OMR), Pune (Hinjewadi), Mumbai
(Powai), Delhi NCR (Noida), and Kolkata (Salt Lake). These names do not identify
real colleges.

The seed also includes 27 fictional resources across the institutions, 40
fictional users, training records, historical bookings, pending and waitlisted
requests, incidents, and audit events. The city summary exposes only sample
city names, per-city resource and organization counts, and catalog categories.
All seeded people, records, and statistics are synthetic; they are not live
institutional data.

The resource catalog supports city, area, organization, category, and text
filters in addition to the other supported catalog filters. Requesters can
discover resources across organizations; managers' resource-management scope
is restricted by the backend to their organization.

## Booking assistant

The assistant is available to authenticated requesters and lab managers. Its
deterministic rules engine handles resource discovery, requirements and
eligibility explanations, alternatives, the signed-in requester's own request
outcomes, and request-draft preparation.

An optional OpenAI-compatible model layer can interpret a message as a
structured intent and help phrase the response. It is enabled only when
`AI_API_KEY` and a supported `AI_PROVIDER` are configured. Without a configured
provider, the assistant uses the rules engine. The model layer does not decide
eligibility, approval, waitlisting, or policy outcomes. Resource access,
eligibility checks, and final state changes remain backend responsibilities.

The assistant never submits a request itself. A user must explicitly confirm a
draft through the standard request endpoint. The backend evaluates eligibility
and records the result; only an authorized human manager can approve or
waitlist an eligible pending request. The assistant cannot approve a request or
override training, eligibility, or other rules.

## Limitations

- No real institutional identity provider, student information system,
  training registry, facilities system, or calendar is integrated.
- Seeded organizations, people, resources, bookings, training, incidents, and
  audit entries are fictional demo data.
- Access-model labels are informational; there is no payment processing,
  deposit, or fine workflow.
- The assistant cannot approve or allocate requests and cannot override
  eligibility or safety rules.
- The model layer is inactive when no API key is configured; rules-based
  assistance remains available.
- A confirmed assistant draft is still only a request. It is not a booking
  unless a manager approves it.

## Development checks

Run backend tests from `backend/` with the test environment values and
dependencies documented in [`../backend/README.md`](../backend/README.md):

```powershell
python -m pytest -q
```

Run frontend validation from `frontend/`:

```powershell
npm run build
npm test
```
