# OpenVault Build Contract

**Product setting:** Northstar Engineering Lab (DEMO), one fictional engineering-college laboratory.  
**Status:** implementation contract for the 48-hour CodeVerse India build.  
**Source of truth:** `OpenVault_Build_Pack.md`, subject to the fixed decisions recorded in this contract.  
**Architecture:** modular monolith; backend owns permissions, eligibility, and state transitions.

**Stack:** Python, FastAPI, Pydantic, SQLAlchemy, pytest; React, TypeScript, Vite, Tailwind; SQLite locally and PostgreSQL when deployed.

Types and required fields below define the implementation contract. Remaining decisions not specified by the build pack or this contract are marked **OPEN**. Section 18 resolves the decisions listed in Section 17 and takes precedence over any earlier conflicting wording. JSON columns use structured, schema-validated data; timestamps are stored as UTC ISO-8601 and displayed in Asia/Kolkata (IST).

## 1. SCOPE

### P0 - required for a working core

| Requirement | Contract outcome |
|---|---|
| Role-based demo login / controlled demo accounts | Demo identities have server-assigned roles; clients cannot select a role in request bodies. |
| Resource CRUD with status, location, availability, policy, and requirements | Persist resource changes and show them after refresh. |
| Search/filter and resource detail | Search by capability/category and show requirements, eligibility blockers, readiness, and availability. |
| Eligibility/readiness engine | Server rejects blocked requests with exact blocker codes and messages. |
| Booking request and human approval/rejection/waitlist | Persist the decision, reviewer, reason, time, and resulting state. |
| Conflict-safe scheduling | Never confirm overlapping bookings for the same exclusive resource, including concurrent submissions. |
| Access Contract snapshot | Keep the approved conditions and policy version inspectable and unchanged by later policy edits. |
| Check-in/check-out and condition reports | Require the correct booking; persist reports/evidence metadata; reject duplicate or invalid transitions. |
| Incident workflow | Report, review, respond, and resolve/dismiss only through authorized human actions. |
| Audit event timeline | Critical transitions create server-side audit events; API cannot edit or delete history. |
| Resource Memory basic metrics | Derive metrics from persisted records and show a DEMO DATA disclaimer. |
| Judge route, seeded data, and reset instructions | Judge can complete the scenario; reset is restricted to the demo/admin environment. |

### P1 - only after P0 is stable

| Requirement from pack | Contract outcome |
|---|---|
| Natural-language resource matching | Optional; the only AI feature allowed in this build. Use deterministic hard filters and fallback. |
| Natural-language policy draft | Excluded by the fixed AI boundary; policy editing/activation remains an authorized human action. |
| AI incident summary | Excluded by the fixed AI boundary. Incident handling remains human-led. |
| Notifications/reminders | In-app notifications for decisions and overdue states; no external delivery integration. |

### P2 - defer

The pack's P2 items are cross-institution federation, payments, calendar sync, and QR device integration. Do not attempt these unless all P0 acceptance tests pass and time remains; the fixed scope excludes them regardless of remaining time.

### Explicitly out of scope

- More than one institution/lab, public cross-campus marketplace, or federation.
- Payments, deposits, fines, and automated penalties.
- Real identity verification or integration with institutional identity systems.
- Biometrics, face recognition, live hardware control, and IoT.
- AI policy drafting, AI incident summarization, autonomous approvals, or AI-driven training waivers, maintenance clearance, blame, liability, or penalties.
- Real student data, sensitive training documents, or unnecessary personal data.
- Claims of measured utilization increase, savings, or incident prevention without a real measured pilot.
- A deployed multi-agent runtime. AI is optional and restricted to resource matching.

## 2. ROLES AND PERMISSION MATRIX

The authenticated demo user's server-side identity determines the role and scope on every request. Never accept role, actor ID, or organization scope as authority from the request body. `Own records` means only records belonging to the authenticated requester; object-level checks still apply. A requester cannot approve their own request by default.

Legend: **Allowed** = role may perform it within its assigned scope; **Own records** = requester may perform/read only their own; **Denied** = role cannot perform it.

| Action | Requester | Resource owner / lab manager | Institution admin | Judge / read-only auditor |
|---|---|---|---|---|
| Sign in / sign out | Allowed | Allowed | Allowed | Allowed |
| Search resources and view resource details | Allowed | Allowed | Allowed | Allowed |
| View own requests, decisions, contracts, bookings, and notifications | Own records | Allowed | Allowed | Allowed (read-only demo records) |
| View another requester's personal record | Denied | Allowed only for resources in manager scope | Allowed for institutional administration/audit scope | Allowed read-only for demo records |
| Create/edit a resource | Denied | Allowed for owned/assigned resources | Allowed | Denied |
| Create/edit a structured policy draft | Denied | Allowed for owned/assigned resources | Allowed for policy administration | Denied |
| Activate a policy version | Denied | Allowed for owned/assigned resources, with reason | Denied | Denied |
| Record/verify training sign-off | Denied | Allowed within manager scope | Denied unless separately assigned the manager role | Denied |
| Submit/cancel own request | Own records | Own records if also acting as requester is not permitted by this single-role model | Denied | Denied |
| Approve/reject/waitlist a request | Denied | Allowed for managed resources, never own request | Denied unless separately assigned manager role | Denied |
| Check in/out and submit condition report | Own records | Denied as requester action; manager may review handover | Denied | Denied |
| Report an incident / respond to an incident | Own records | Allowed for incidents in manager scope | Denied unless separately assigned manager role | Denied |
| Resolve/dismiss an incident | Denied | Allowed for incidents in manager scope | Denied unless separately assigned manager role | Denied |
| View resource timeline / Resource Memory | Allowed | Allowed | Allowed | Allowed read-only |
| View audit events | Own related events only | Allowed within manager scope | Allowed | Allowed read-only |
| Mark own notification read | Own records | Own records | Own records | Own records |
| Reset demo data | Denied | Denied | Allowed only in restricted demo environment | Denied |
| Invoke resource matching | Allowed | Allowed | Allowed | Denied |
| Invoke policy drafting or AI incident summary | Denied | Denied | Denied | Denied |

The pack does not define whether an admin can act as a manager. The default above denies manager-only actions to an admin unless that authenticated demo account has the manager role; one user must not acquire both roles from request data.

## 3. DATA MODEL

All records have a UUID primary key unless a field below identifies a natural key. Persist timestamps in UTC. Use SQLAlchemy relationships and foreign keys; use JSON for structured snapshots, not for values that require filtering/indexing. `is_demo` is true on seeded business records and audit/notification records derived from them; it must never be treated as a security boundary.

### User

| Field | Type / nullability | Constraints / meaning |
|---|---|---|
| `id` | UUID, NOT NULL | Primary key; seeded IDs are deterministic and defined by the seed script. |
| `display_name` | String, NOT NULL | Synthetic display name only. |
| `role` | Enum string, NOT NULL | `requester`, `lab_manager`, `institution_admin`, or `auditor`; assigned server-side. |
| `organization_id` | String, NOT NULL | For this build, the single demo organization identifier for Northstar Engineering Lab. |
| `is_demo` | Boolean, NOT NULL | Seeded identities are true. |
| `password_hash` | String, NOT NULL | Hashed shared demo password; never store or return the plaintext password. |

Relationships: one-to-many to requests, training records, bookings through requests, handover reports as actor, incidents as reporter/responder where applicable, audit events as actor, and notifications as recipient. Unique/index: unique `(organization_id, display_name)`; index `(organization_id, role)`. Login selects the seeded account by ID and verifies the shared password against `password_hash`.

### Resource

| Field | Type / nullability | Constraints / meaning |
|---|---|---|
| `id` | UUID, NOT NULL | Primary key. |
| `owner_id` | UUID FK User, NOT NULL | Resource owner/manager identity. |
| `name` | String, NOT NULL | Display name. |
| `category` | String, NOT NULL | Search/filter category. |
| `capability_tags` | JSON array of strings, NOT NULL | Searchable capabilities. |
| `location` | String, NOT NULL | Lab location. |
| `status` | Enum string, NOT NULL | `active` or `maintenance_hold`. |
| `hold_review_date` | Date, nullable | Required when status is `maintenance_hold` (`CHECK status != 'maintenance_hold' OR hold_review_date IS NOT NULL`); review date does not automatically clear the hold. |
| `weekly_operating_hours` | JSON array, NOT NULL | Entries `{weekday, start, end}` in Asia/Kolkata local time; `weekday` is ISO weekday 1-7 and times are local `HH:MM`. Convert request instants from UTC for comparison. |
| `max_duration_minutes` | Integer, nullable | Upper bound when configured; positive when present. |
| `exclusive_booking` | Boolean, NOT NULL | All six seeded resources set this to true. |
| `is_demo` | Boolean, NOT NULL | Seeded resources are true. |

Relationships: belongs to User owner; has many policies, requests, and bookings through requests. Constraints/indexes: check status is `active` or `maintenance_hold`; check a maintenance hold has a review date; index `(category, status)`, owner FK, and capability search strategy as supported by the selected database. Resource names are not required to be globally unique.

### ResourcePolicy

| Field | Type / nullability | Constraints / meaning |
|---|---|---|
| `id` | UUID, NOT NULL | Primary key and policy-version identifier. |
| `resource_id` | UUID FK Resource, NOT NULL | Parent resource. |
| `version` | Integer, NOT NULL | Positive, monotonically increasing per resource. |
| `structured_requirements` | JSON object, NOT NULL | Exact schema: `{"training_codes":[],"supervisor_required":false,"supervised_windows":[]}`. Each supervised window is `{weekday,start,end}` in Asia/Kolkata local time, ISO weekday 1-7 and local `HH:MM`. |
| `allowed_uses` | JSON array of enum strings, NOT NULL | Values are `project`, `coursework`, and `research`. |
| `priority_policy` | JSON object, NOT NULL | Exact initial value `{}`. Allocation constants are fixed by Section 7, not configurable here. |
| `effective_at` | UTC timestamp, nullable | Null until activation; set when activated. |
| `approved_by` | UUID FK User, nullable | Null while draft; scoped lab manager who activated the version. |
| `activation_reason` | Text, nullable | Required when a manager activates the version. |
| `is_demo` | Boolean, NOT NULL | True for seeded policy versions. |

Relationships: belongs to Resource; referenced by AllocationDecision and AccessContract. Unique `(resource_id, version)`; index `(resource_id, effective_at)`. Editing always creates a new version. Only a scoped lab manager activates a version, with a reason; activation must not mutate previous policy data.

### TrainingRecord

| Field | Type / nullability | Constraints / meaning |
|---|---|---|
| `id` | UUID, NOT NULL | Primary key. |
| `user_id` | UUID FK User, NOT NULL | Trainee. |
| `requirement_code` | String, NOT NULL | Must match a policy requirement code exactly. |
| `status` | Enum string, NOT NULL | `valid`, `expired`, or `revoked`; final vocabulary is OPEN. |
| `verified_by` | UUID FK User, nullable | Authorized manager who recorded the sign-off; required for a valid record. |
| `valid_from` | UTC timestamp, NOT NULL | Start of validity. |
| `valid_to` | UTC timestamp, nullable | Null means no expiry only if policy explicitly permits it; expiry policy is OPEN. |
| `is_demo` | Boolean, NOT NULL | Synthetic records are true. |

Relationships: belongs to trainee User and optional verifier User. Index `(user_id, requirement_code, status, valid_to)`; duplicate active sign-offs for the same user/code require a defined policy and are otherwise not unique.

### ResourceRequest

| Field | Type / nullability | Constraints / meaning |
|---|---|---|
| `id` | UUID, NOT NULL | Primary key. |
| `requester_id` | UUID FK User, NOT NULL | Authenticated requester; never supplied as authority by the client. |
| `resource_id` | UUID FK Resource, NOT NULL | Requested resource. |
| `purpose` | Text, NOT NULL | User-stated project purpose; no sensitive personal data. |
| `start_at` | UTC timestamp, NOT NULL | Requested interval start. |
| `end_at` | UTC timestamp, NOT NULL | Requested interval end; must be after start. |
| `status` | Enum string, NOT NULL | Request lifecycle state in Section 4. |
| `created_at` | UTC timestamp, NOT NULL | Server-set creation time. |
| `idempotency_key` | String, nullable | Client retry key; unique per requester when present. |
| `is_demo` | Boolean, NOT NULL | Seeded requests are true. |

Relationships: belongs to requester and resource; has decisions; has at most one Booking. Indexes `(requester_id, created_at)`, `(resource_id, start_at, end_at, status)`, and unique `(requester_id, idempotency_key)` when key is non-null.

### AllocationDecision

| Field | Type / nullability | Constraints / meaning |
|---|---|---|
| `id` | UUID, NOT NULL | Primary key. |
| `request_id` | UUID FK ResourceRequest, NOT NULL | Request being evaluated. |
| `decision_sequence` | Integer, NOT NULL | Monotonically increasing per request; supports a waitlisted request returning for a later human decision. |
| `policy_version` | UUID FK ResourcePolicy, NOT NULL | Exact policy used. |
| `outcome` | Enum string, NOT NULL | `approved`, `rejected`, or `waitlisted`. |
| `explanation_code` | String, NOT NULL | Stable reason code. |
| `explanation` | Text, NOT NULL | Human-readable explanation shown to the requester. |
| `inputs_snapshot` | JSON object, NOT NULL | Eligibility, competing requests, usage inputs, policy parameters, and algorithm version used. |
| `reviewer_override` | JSON object, nullable | If present, records override flag and required human reason; never an AI decision. |
| `reviewer_id` | UUID FK User, NOT NULL | Human decision-maker. |
| `created_at` | UTC timestamp, NOT NULL | Server-set decision time. |
| `is_demo` | Boolean, NOT NULL | True when decision is seeded/demo. |

Relationships: belongs to request, policy version, and reviewer. Decisions are append-only; unique `(request_id, decision_sequence)` and index `(request_id, created_at)`, `(reviewer_id, created_at)`, and `(policy_version, outcome)`. The latest decision is current; prior waitlist/review outcomes remain auditable.

### Booking

| Field | Type / nullability | Constraints / meaning |
|---|---|---|
| `id` | UUID, NOT NULL | Primary key. |
| `request_id` | UUID FK ResourceRequest, NOT NULL | Approved request; unique, at most one booking per request. |
| `start_at` | UTC timestamp, NOT NULL | Confirmed interval start. |
| `end_at` | UTC timestamp, NOT NULL | Confirmed interval end; after start. |
| `status` | Enum string, NOT NULL | Booking state in Section 4. |
| `approved_by` | UUID FK User, NOT NULL | Human approver. |
| `version` | Integer, NOT NULL | Starts at 1; increments only through explicit amendment, if enabled. |
| `is_demo` | Boolean, NOT NULL | True for seeded bookings. |

Relationships: one-to-one with ResourceRequest; has AccessContract, handover reports, and incidents. Index `(status, start_at, end_at)` and `(request_id)` unique. Overlap protection is a transaction/service rule plus the strongest database constraint supported by the selected DB.

### AccessContract

| Field | Type / nullability | Constraints / meaning |
|---|---|---|
| `id` | UUID, NOT NULL | Primary key. |
| `booking_id` | UUID FK Booking, NOT NULL | Parent booking. |
| `version` | Integer, NOT NULL | Starts at 1; later amendments create a new version, never overwrite. |
| `request_id` | UUID FK ResourceRequest, NOT NULL | Snapshot source. |
| `resource_id` | UUID FK Resource, NOT NULL | Snapshot resource. |
| `requester_id` | UUID FK User, NOT NULL | Snapshot requester. |
| `approver_id` | UUID FK User, NOT NULL | Snapshot approver. |
| `start_at`, `end_at` | UTC timestamp, NOT NULL | Approved booking interval. |
| `approved_purpose` | Text, NOT NULL | Purpose at approval. |
| `policy_version_id` | UUID FK ResourcePolicy, NOT NULL | Immutable policy version reference. |
| `requirements_snapshot` | JSON object, NOT NULL | Requirements at approval. |
| `supervision_requirement` | Boolean, NOT NULL | Requirement at approval. |
| `permitted_use` | JSON array of strings, NOT NULL | Permitted uses at approval. |
| `checkin_required`, `checkout_required` | Boolean, NOT NULL | Approved conditions. |
| `condition_checklist_version` | String, NOT NULL | Checklist used for this booking. |
| `status` | Enum string, NOT NULL | `ACTIVE`, `COMPLETED`, or `CANCELLED`. |
| `created_at`, `approved_at` | UTC timestamp, NOT NULL | Server-set creation and approval times. |
| `expires_at` | UTC timestamp, NOT NULL | Equals the approved Booking `end_at`. |
| `is_demo` | Boolean, NOT NULL | True for seeded contracts. |

Relationships: belongs to Booking, ResourceRequest, Resource, Requester, Approver, and ResourcePolicy. Unique `(booking_id, version)`; index `(booking_id, version)`. The approved snapshot fields are append-only. There are no amendments; a re-approval creates a new contract version.

### HandoverReport

| Field | Type / nullability | Constraints / meaning |
|---|---|---|
| `id` | UUID, NOT NULL | Primary key. |
| `booking_id` | UUID FK Booking, NOT NULL | Active booking being handed over/returned. |
| `stage` | Enum string, NOT NULL | `IN` or `OUT`. |
| `checklist_version` | String, NOT NULL | Same versioned checklist definition for both stages. |
| `condition` | JSON object, NOT NULL | Exact fields: `physical_condition` (`ok`, `minor_wear`, `damaged`), `accessories_complete` (`yes`, `no`), `functional_test` (`works`, `issue`), and `notes` (string or null). The same checklist/version is used for IN and OUT. |
| `notes` | Text, nullable | Neutral factual notes. |
| `evidence_references` | JSON array, NOT NULL | Metadata only: `file_name` and `note`; no binary upload or public URL. |
| `actor_id` | UUID FK User, NOT NULL | Authenticated report author. |
| `created_at` | UTC timestamp, NOT NULL | Server timestamp. |
| `is_demo` | Boolean, NOT NULL | True for seeded reports. |

Relationships: belongs to Booking and actor User. Unique `(booking_id, stage)` prevents duplicate check-in/out reports; index `(actor_id, created_at)`.

### Incident

| Field | Type / nullability | Constraints / meaning |
|---|---|---|
| `id` | UUID, NOT NULL | Primary key. |
| `booking_id` | UUID FK Booking, NOT NULL | Related booking. |
| `reporter_id` | UUID FK User, NOT NULL | Incident reporter. |
| `category` | Enum string, NOT NULL | `damage`, `missing_part`, `malfunction`, `late_return`, or `other`. |
| `description` | Text, NOT NULL | Reporter-authored neutral description. |
| `status` | Enum string, NOT NULL | `OPEN`, `INFORMATION_REQUESTED`, `UNDER_REVIEW`, `RESOLVED`, or `DISMISSED`. |
| `responses` | JSON array, NOT NULL | Append-only response records with actor, text, and server timestamp. |
| `resolution` | JSON object, nullable | Human rationale and resolution outcome; no blame/penalty determination. |
| `reviewer_id` | UUID FK User, nullable | Authorized human resolver/dismisser. |
| `created_at`, `updated_at` | UTC timestamp, NOT NULL | Server-managed. |
| `is_demo` | Boolean, NOT NULL | True for seeded incidents. |

Relationships: belongs to Booking, Reporter, and optional Reviewer. Index `(status, created_at)`, `(booking_id)`, `(reporter_id)`.

### AuditEvent

| Field | Type / nullability | Constraints / meaning |
|---|---|---|
| `id` | UUID, NOT NULL | Primary key. |
| `actor_id` | UUID FK User, nullable | Authenticated actor; null only for server-originated events without a user. |
| `entity_type` | String, NOT NULL | Entity kind. |
| `entity_id` | UUID, NOT NULL | Related entity ID; polymorphic reference, indexed. |
| `action` | String, NOT NULL | Critical action/event name. |
| `timestamp` | UTC timestamp, NOT NULL | Server-set time. |
| `request_id` | String, nullable | Correlation/request identifier. |
| `correlation_id` | String, nullable | Related workflow correlation identifier. |
| `before_summary`, `after_summary` | JSON object, nullable | Minimal non-sensitive transition summaries. |
| `previous_hash`, `hash` | String, nullable | Optional tamper-evident linkage only; not blockchain or legal proof. |
| `is_demo` | Boolean, NOT NULL | True for seeded events. |

Relationships: optional Actor User; polymorphic entity reference. Indexes `(entity_type, entity_id, timestamp)`, `(actor_id, timestamp)`, and `(correlation_id)`. Append-only through application and database permissions; no update/delete API.

### Notification

| Field | Type / nullability | Constraints / meaning |
|---|---|---|
| `id` | UUID, NOT NULL | Primary key. |
| `recipient_id` | UUID FK User, NOT NULL | Recipient. |
| `type` | String, NOT NULL | In-app type: `decision`, `waitlist_promotion`, `cancellation`, `checkin_due`, or read-time `overdue_return`. |
| `related_entity_type` | String, NOT NULL | Related entity kind. |
| `related_entity_id` | UUID, NOT NULL | Related entity identifier. |
| `read_at` | UTC timestamp, nullable | Null until recipient marks it read. |
| `created_at` | UTC timestamp, NOT NULL | Server-set time. |
| `is_demo` | Boolean, NOT NULL | True for seeded notifications. |

Relationships: belongs to recipient User; polymorphic related entity. Unique `(recipient_id, type, related_entity_type, related_entity_id)` prevents duplicate transition/reminder notifications; index `(recipient_id, read_at, created_at)`.

### ER-style relationship diagram

```text
User (owner) 1 --- * Resource 1 --- * ResourcePolicy
User (requester) 1 --- * ResourceRequest * --- 1 Resource
ResourceRequest 1 --- * AllocationDecision * --- 1 ResourcePolicy
ResourceRequest 1 --- 0..1 Booking 1 --- 1..* AccessContract (versioned)
Booking 1 --- 0..2 HandoverReport
Booking 1 --- * Incident
User 1 --- * TrainingRecord
User 1 --- * Notification
User 1 --- * AuditEvent (actor; nullable for system event)
User (reporter/reviewer/actor) --- Incident / HandoverReport
AuditEvent.entity_type + entity_id and Notification.related_entity_type + related_entity_id
    are polymorphic references, not cross-table foreign keys.
```

## 4. STATE MACHINES

All transitions are checked centrally in the backend. A transition and its audit event are committed atomically. Roles below assume the role/scope rules in Section 2. `invalid_state` is returned for a recognized action that is illegal from the current state; `forbidden` is returned when the actor lacks authority.

### Request

`DRAFT -> SUBMITTED -> INELIGIBLE | PENDING_REVIEW`  
`PENDING_REVIEW -> APPROVED | REJECTED | WAITLISTED`  
`WAITLISTED -> PENDING_REVIEW | CANCELLED | EXPIRED`  
`APPROVED -> CANCELLED`

| From -> To | Triggering role | Preconditions | Audit event |
|---|---|---|---|
| Create -> `DRAFT` | Requester | Authenticated; resource exists. | `request.created` |
| `DRAFT` -> `SUBMITTED` | Requester | Valid interval, purpose, resource; server readiness/eligibility evaluated. | `request.submitted` |
| `SUBMITTED` -> `INELIGIBLE` | Server | Eligibility check finds one or more blockers. | `request.ineligible` |
| `SUBMITTED` -> `PENDING_REVIEW` | Server | Eligibility passes; request can be considered by a human. | `request.queued_for_review` |
| `PENDING_REVIEW` -> `APPROVED` | Manager | Eligibility rechecked; no maintenance hold/conflict; no self-approval; human reason; decision persisted; booking and immutable contract created atomically. | `request.approved` |
| `PENDING_REVIEW` -> `REJECTED` | Manager | Human reason required. | `request.rejected` |
| `PENDING_REVIEW` -> `WAITLISTED` | Manager | Eligible request; policy allows waitlist; reason recorded. | `request.waitlisted` |
| `WAITLISTED` -> `PENDING_REVIEW` | Manager | Slot/open capacity is now reviewable; eligibility rechecked. | `request.promoted_to_review` |
| `WAITLISTED` -> `CANCELLED` | Requester | Request belongs to actor. | `request.cancelled` |
| `WAITLISTED` -> `EXPIRED` | Server | Requested slot start time is reached. | `request.expired` |
| `APPROVED` -> `CANCELLED` | Requester or manager | Cancellation occurs at least 2 hours before start; slot release and audit commit atomically. | `request.cancelled` |

`INELIGIBLE`, `REJECTED`, `CANCELLED`, and `EXPIRED` have no outgoing request transitions. Resubmission requires a new request. Check-in, return, closure, and no-show belong only to Booking, not Request. `DRAFT` is created and submitted within the request-submission transaction; draft deletion and post-submission edits are not supported.

### Booking

Booking is created only when a request is approved. It mirrors operational use without replacing the Request lifecycle.

`CONFIRMED -> CANCELLED | CHECKED_IN | NO_SHOW`  
`NO_SHOW -> CHECKED_IN` (late check-in before booking end)  
`CHECKED_IN -> RETURN_PENDING -> CLOSED | INCIDENT_REVIEW -> CLOSED`

| From -> To | Triggering role | Preconditions | Audit event |
|---|---|---|---|
| Create -> `CONFIRMED` | Manager approval transaction | Request approved, eligibility passes, interval conflict check passes, contract snapshot created. | `booking.confirmed` |
| `CONFIRMED` -> `CANCELLED` | Requester or manager | Cancellation occurs at least 2 hours before start; slot release and audit in same transaction. | `booking.cancelled` |
| `CONFIRMED` -> `CHECKED_IN` | Requester | Correct booking and requester; `start_at - 15 minutes <= now < end_at`; server eligibility and maintenance checks pass; unique IN report. | `booking.checked_in` |
| `CONFIRMED` -> `NO_SHOW` | Server | Current time is at least 30 minutes after start and no check-in exists. | `booking.no_show` |
| `NO_SHOW` -> `CHECKED_IN` | Requester | No-show was recorded at start + 30 minutes, but current time is still before booking end; eligibility and maintenance are rechecked and no IN report exists. The no-show event remains in history/metrics. | `booking.late_checked_in` |
| `CHECKED_IN` -> `RETURN_PENDING` | Requester | Correct active booking; unique OUT report; no prior checkout. | `booking.checked_out` |
| `RETURN_PENDING` -> `CLOSED` | Server | No return discrepancy. | `booking.closed` |
| `RETURN_PENDING` -> `INCIDENT_REVIEW` | Server | Discrepancy captured; incident created. | `booking.incident_review_opened` |
| `INCIDENT_REVIEW` -> `CLOSED` | Manager | Linked incident is resolved/dismissed by an authorized reviewer. | `booking.closed_after_review` |

The manager cannot check in/out on behalf of a requester through these endpoints. Cancellation after the two-hour cutoff is invalid for requester and manager. Extensions are not part of this build.

### Incident

States: `OPEN`, `INFORMATION_REQUESTED`, `UNDER_REVIEW`, `RESOLVED`, `DISMISSED`.

| From -> To | Triggering role | Preconditions | Audit event |
|---|---|---|---|
| Create -> `OPEN` | Requester or manager | Related valid booking; neutral description/category provided. | `incident.opened` |
| `OPEN` -> `INFORMATION_REQUESTED` | Manager | Authorized manager; request for information recorded. | `incident.information_requested` |
| `OPEN` -> `UNDER_REVIEW` | Manager | Authorized manager begins review. | `incident.review_started` |
| `INFORMATION_REQUESTED` -> `UNDER_REVIEW` | Manager | Response received or manager elects to continue; response remains append-only. | `incident.review_started` |
| `UNDER_REVIEW` -> `INFORMATION_REQUESTED` | Manager | Additional information is needed; reason recorded. | `incident.information_requested` |
| `UNDER_REVIEW` -> `RESOLVED` | Manager | Human resolution rationale required; no automated guilt, liability, or penalty. | `incident.resolved` |
| `UNDER_REVIEW` -> `DISMISSED` | Manager | Human dismissal rationale required. | `incident.dismissed` |

Responses append to the incident while OPEN, INFORMATION_REQUESTED, or UNDER_REVIEW; reporter/requester and manager may respond on an authorized incident. Resolution/dismissal is manager-only. `RESOLVED` and `DISMISSED` are terminal. Reopening is not defined.

### Explicit illegal transitions

The following must return `invalid_state` (unless role/scope fails first, in which case return `forbidden`):

| Illegal action | Example |
|---|---|
| Approve/reject a request not in `PENDING_REVIEW` | Approve a waitlisted, rejected, or already approved request. |
| Transition an `INELIGIBLE`, `REJECTED`, `CANCELLED`, or `EXPIRED` request | Reuse a terminal request instead of creating a new one. |
| Cancel after the two-hour cutoff | Cancellation timestamp is strictly later than `start_at - 2 hours`; the exact cutoff instant is allowed. |
| Check in without an approved/confirmed, active booking | Draft request, wrong booking, canceled/no-show booking, before the 15-minute window, or after booking end. |
| Check in at or after booking end | Check-in window has closed; no transition from `CONFIRMED` or `NO_SHOW` is allowed. |
| Duplicate check-in or check-out | Existing unique IN/OUT report or already advanced state. |
| Check out before check-in | No matching active checked-in booking. |
| Close a return with an unresolved discrepancy | Booking must remain in incident review. |
| Resolve/dismiss an incident outside `UNDER_REVIEW` | Incident is open, information-requested, or terminal. |
| Add a response to a terminal incident | Resolved or dismissed incident. |
| Activate an already superseded policy version or edit an active version in place | Create a new policy version; a manager activates it with a reason. |

## 5. INVARIANTS (MUST NEVER BREAK)

| Invariant | Enforcement | Proving test |
|---|---|---|
| No two confirmed overlapping bookings for the same exclusive resource. | Treat intervals as half-open `[start_at, end_at)`. Run overlap check and confirmation in one transaction; SQLite uses `BEGIN IMMEDIATE`, PostgreSQL locks the resource row with `SELECT FOR UPDATE`. | Two concurrent overlapping approvals for one exclusive resource: at most one commits; adjacent non-overlapping intervals both succeed on SQLite and PostgreSQL. |
| A resource on maintenance hold cannot be approved or checked in. | Service-layer status check inside approval/check-in transaction; re-read resource status at commit. | Maintenance-held resource approval and check-in both fail with `ineligible` and `maintenance_hold`. |
| Eligibility is rechecked server-side at submission, approval, and check-in. | Shared eligibility service invoked at each transition; client result is informational only. | Missing/expired training blocks at each of the three operations, including a record that expires after submission. |
| No self-approval by default. | Compare authenticated requester ID with authenticated reviewer ID in the decision service; no request-body actor override. | Test setup directly creates a manager's own request (not through the API); that manager's approval returns `forbidden`, while another authorized manager can approve an eligible request. |
| Check-in/out references the correct active booking and cannot be duplicated. | Booking/requester relationship and state validation; unique `(booking_id, stage)` report constraint; transaction. | Wrong user's booking fails; repeated IN or OUT fails; out-before-in fails. |
| Policy edits never alter an existing AccessContract snapshot. | Immutable snapshot columns; policy edits create a new version; amendments create a new contract version or explicit amendment event. | Approve, edit/activate a later policy, then assert original contract snapshot and version unchanged. |
| A return-condition discrepancy creates a reviewable incident, never automatic fault or penalty. | Handover service creates incident + review state atomically; schema has no automatic fault/penalty action. | OUT discrepancy creates incident in OPEN/UNDER_REVIEW path; no blame/fine/penalty field or action is set. |
| Audit events are server-created for every critical transition and cannot be edited/deleted through API. | Audit helper called within same transaction as transition; append-only database permissions/API surface; no update/delete route. | Critical-action tests assert corresponding event; API attempts to update/delete audit event are forbidden/not found. |
| AI output is untrusted and schema-validated. | Strict Pydantic schema, timeout, allowed-resource-ID validation, deterministic fallback; AI cannot call transition services. | Malformed JSON, timeout, unknown IDs, or unsafe fields produce fallback/no state change. |

## 6. READINESS AND ELIGIBILITY ENGINE

The backend is authoritative. Compute readiness for a requested interval and actor using exactly these inputs:

| Input field/source | Purpose |
|---|---|
| `Resource.status` and `Resource.hold_review_date` | Active versus maintenance hold; review date is informational and never auto-clears the hold. |
| Current `ResourcePolicy` existence, `effective_at`, `approved_by`, `structured_requirements`, `allowed_uses` | Detect missing/unapproved policy; read `training_codes[]`, `supervisor_required`, and weekly `supervised_windows[]`. |
| ResourcePolicy supervised windows | Enforce supervision for the requested interval. Weekly windows use Asia/Kolkata local weekday and `HH:MM` values. |
| User's `TrainingRecord.requirement_code`, `status`, `verified_by`, `valid_from`, `valid_to` | Verify each required training prerequisite at evaluation time. |
| Request `purpose`, `start_at`, `end_at`, `created_at` | Check allowed use, valid interval, duration, and allocation ordering. |
| Resource `max_duration_minutes` | Enforce configured maximum duration. |
| Existing confirmed Booking intervals and `Resource.exclusive_booking` | Detect schedule conflict. |
| `Resource.weekly_operating_hours` | Check requested slot availability; entries are `{weekday,start,end}` in Asia/Kolkata local time. |
| Booking `start_at`, `end_at`, and current time | Check-in is permitted from `start_at - 15 minutes` inclusive until `end_at` exclusive. |

Evaluate all applicable blockers, not only the first. Return a deterministic ordered list using this order: policy missing, maintenance hold, missing training, supervisor unavailable, slot conflict. The list order is presentation only; any blocker prevents approval.

| Code | Human-readable message | Authorized next action |
|---|---|---|
| `policy_missing` | `This resource is not ready for self-service because its access policy is missing or not approved.` | Resource owner/lab manager reviews and activates a policy version. |
| `maintenance_hold` | `This resource is on maintenance hold and cannot be booked.` | Resource owner/lab manager reviews the hold; do not auto-release it. |
| `missing_training` | `Required training is missing, expired, or not verified for this resource.` Include the exact requirement code/name in details. | Requester asks the authorized training owner; manager records a verified sign-off. AI cannot waive it. |
| `supervisor_unavailable` | `A required supervisor is not available for this time slot.` | Requester chooses a covered slot; manager records/arranges coverage. |
| `slot_conflict` | `This time slot conflicts with a confirmed booking for this resource.` | Requester selects a free slot or asks for the waitlist when policy allows. |

Submission returns all blockers with code, message, and permitted next action. Approval and check-in recompute against current records and do not trust cached client eligibility. `ineligible` is the top-level error code; `details` contains one or more blocker codes.

## 7. ALLOCATION POLICY

Deterministic policy only; no opaque fairness score. Eligibility and hard constraints run before ranking. A human manager makes the final decision for every approval/rejection/waitlist action.

1. **Hard filter:** reject eligibility failures, disallowed purpose, invalid duration, maintenance hold, unavailable supervision, and confirmed-slot conflict. Do not rank ineligible requests.
2. **Protect confirmations:** confirmed bookings never lose their slot due to a later request.
3. **No priority tiers:** the initial `priority_policy` is `{}`; use only the fixed newcomer, usage, and queue-age rules below. Do not infer identity-based priority.
4. **First-access path:** among otherwise eligible competing requests, a requester with zero completed bookings for that resource in the preceding 30 days is a newcomer and is preferred.
5. **Usage limit:** enforce at most 10 booked hours per user per resource in the rolling 30-day window. Count booking hours, not check-in duration. The limit is a hard constraint unless a lab manager explicitly overrides it with a recorded audit reason.
6. **Usage fairness:** among remaining eligible competing requests, prefer the lower booked-hour total for that resource in the preceding 30 days.
7. **Queue age:** for equal newcomer and usage status, prefer the earlier server `created_at`. If still tied, the manager selects and records a reason; do not generate a hidden score or random winner.
8. **Human decision:** manager explicitly approves, rejects, or waitlists, supplies a reason, and may override the recommendation or usage limit with an audit reason. System recommendation alone never creates a booking.

There are no priority tiers. `priority_policy` is `{}` in the initial policy. An eligible request is not treated as conflicting solely because another unapproved request asks for the same interval; manager approval rechecks confirmed bookings transactionally, and only one overlapping booking can be confirmed. Competing eligible requests are ranked by the rules above.

### AllocationDecision input snapshot

Persist: request ID/resource ID/requester ID; request purpose and interval; policy ID/version and `priority_policy`; fixed 30-day usage window, 10-hour limit, and newcomer rule; eligibility result and blocker codes; maintenance/status and supervisor-window result; competing eligible request IDs and their queue times; each contender's newcomer flag, booked-hour total for the preceding 30 days, limit decision, ranking inputs, and relevant confirmed booking intervals; algorithm version; human reviewer; chosen outcome; explanation code/text; override flag/reason; decision timestamp. Do not snapshot unnecessary personal details.

### Requester explanation templates

Substitute values from persisted decision fields; `{reason}` is the manager's recorded reason or the deterministic policy explanation, never invented by the UI.

- **Approved:** `Your request for {resource_name} from {start_at} to {end_at} was approved by {reviewer_name}. Reason: {reason} Access Contract (session conditions) is available for this booking.`
- **Rejected:** `Your request for {resource_name} from {start_at} to {end_at} was not approved. Reason: {reason}`
- **Waitlisted:** `Your request for {resource_name} from {start_at} to {end_at} is waitlisted. Reason: {reason} No booking is confirmed; you will be notified if it moves to review.`

## 8. ACCESS CONTRACT

UI label, exactly: **Access Contract (session conditions)**. It is an application record, not a legal contract.

Snapshot: booking ID; contract version; request/resource/requester/approver IDs; approved interval and purpose; policy version ID; complete requirements snapshot; supervisor requirement/windows; permitted use; check-in/check-out requirements; checklist version; status; created/approved/expiry timestamps. These are captured from the approved request and policy at the approval transaction.

The first approval creates version 1 with status `ACTIVE` and `expires_at = booking.end_at`. Successful return closes it as `COMPLETED`; cancellation closes it as `CANCELLED`. A no-show event does not cancel the contract while late check-in remains possible; if the booking is still a no-show at booking end, close the contract as `CANCELLED`. Policy edits create a new ResourcePolicy version and never change an existing contract. Contract amendments are not supported. A later re-approval creates a new contract version and preserves prior versions.

## 9. HANDOVER AND INCIDENTS

One versioned condition checklist is used for both `IN` and `OUT`; save its `checklist_version` in each HandoverReport. Check-in and check-out record actor, server timestamp, structured condition values, optional neutral notes, and private evidence references. A discrepancy on OUT creates a reviewable incident and moves the booking into incident review; it does not assert fault.

**Evidence rules:** metadata only; no binary upload or public URL. Each evidence item stores `file_name` and `note`. Do not claim or imply that a file was uploaded. Avoid sensitive content in evidence notes and audit summaries.

Checklist fields are `physical_condition` (`ok`, `minor_wear`, `damaged`), `accessories_complete` (`yes`, `no`), `functional_test` (`works`, `issue`), and `notes`. A discrepancy exists when OUT `physical_condition` is worse than IN (`ok < minor_wear < damaged`), OUT `accessories_complete` is `no`, or OUT `functional_test` is `issue`. A discrepancy creates a reviewable incident; it does not assert fault.

For an automatically created discrepancy incident, use `damage` for a physical-condition discrepancy, `missing_part` for incomplete accessories, `malfunction` for a functional-test issue, and `other` when multiple discrepancy categories occur together. `late_return` is available for a human-reported late return; it does not imply fault.

Incident states and transitions are defined in Section 4. Requester/reporter and scoped manager may append a response while the incident is active. Only the scoped lab manager may resolve or dismiss, with written rationale. The institution admin and auditor are read-only for incident resolution unless separately authenticated as a lab manager. No automated fault, blame, liability finding, fine, or penalty is permitted.

## 10. RESOURCE MEMORY (CAPACITY RECOVERY)

Metrics are derived from persisted records and exposed with an explicit range (`from`, `to`). If omitted, use the rolling 30 days ending at the current time. Show `DEMO DATA — not live institutional statistics` whenever the query includes seeded records.

| Metric | Definition/source |
|---|---|
| Available hours | Resource weekly operating hours less blocked/confirmed intervals in the selected range. Operating hours are defined per Resource in Section 3 and interpreted in Asia/Kolkata. |
| Scheduled hours | Duration of confirmed bookings intersecting the range. |
| Completed hours | Duration of closed bookings with a completed handover lifecycle. |
| Cancellations | Count only requests canceled after approval, by cancellation timestamp and range. |
| No-shows | Count persisted `booking.no_show` events: no check-in existed 30 minutes after `start_at`. A later check-in does not erase the no-show event. |
| Blocked hours by reason | Duration unavailable due to maintenance, missing prerequisite/policy, or missing supervisor coverage, grouped by blocker code; only persisted intervals may contribute. Reconstruct maintenance intervals from server-side Resource.status audit transitions; do not infer a hold's start from its review date. |
| Waitlist demand | Count of waitlisted requests and requested hours in range. |
| Maintenance holds | Count and duration of resource maintenance holds in range; use server-side `Resource.status` audit events to bound each hold interval. |
| Unresolved incidents | Count of incidents not RESOLVED or DISMISSED at query time, with creation date in range. |

Do not double-count overlapping blocked intervals. Requests, bookings, holds, and incidents must reconcile to their source rows. Each recommendation contains `recommendation_code`, safe text, `trigger_rule`, required evidence/source record references, source counts, `range_start`, `range_end`, and limitations. Seeded source records have `is_demo=true`; all affected metrics/recommendations are marked DEMO DATA.

Implement the three selected recommendations below as deterministic, source-linked results. The window defaults to the last 30 days and may be explicitly requested by the caller.

| Recommendation | Trigger rule | Required evidence and source counts | Date range | Safe output text |
|---|---|---|---|---|
| Resolve training backlog | At least two distinct users have eligible requests blocked by the same missing training code in the range. | Count distinct affected users and requests by requirement code; identify the authorized training owner; source request/training records. | Selected range or default last 30 days. | `Review the training backlog for {requirement}. {user_count} users across {request_count} requests were blocked during {range}. The authorized training owner is {owner}.` |
| Add a supervised slot | At least two eligible requests in the range were blocked solely because their requested intervals fall outside required supervised windows. | Count requests; include requested weekdays/times and matching policy windows; source request and policy records. | Selected range or default last 30 days. | `Consider adding supervised coverage for {requested_window}. {count} eligible requests in {range} could not proceed because coverage was unavailable. This is a planning suggestion, not an approval.` |
| Review maintenance hold | A resource has `status=maintenance_hold` and `hold_review_date` earlier than the current date. | Count matching holds; list resource IDs, review dates, and blocked hours. | Selected range or default last 30 days, plus the hold review date. | `Review the maintenance hold for {resource_name}; its recorded review date has passed. This does not release the resource automatically.` |

Each recommendation includes `recommendation_code`, safe text, `trigger_rule`, source record references, source counts, `range_start`, `range_end`, and limitations. No recommendation performs the action automatically.

## 11. API CONTRACT

Base path: `/api`. JSON request/response bodies unless a route has no body. IDs are UUID strings; timestamps are UTC ISO-8601. Protected routes use the authenticated server-side demo identity. Role labels in responses are informational only.

API property names use `snake_case`. In the endpoint table, `{...}` means the complete entity projection described in Section 3, not an unrestricted or unspecified object. Responses must not include credentials or public evidence URLs.

### Consistent errors

All errors use:

```json
{
  "error": {
    "code": "ineligible",
    "message": "This resource cannot be booked for the selected request.",
    "details": [{"code": "missing_training", "message": "Required training is missing."}],
    "request_id": "correlation-id"
  }
}
```

| Machine code | HTTP | Meaning |
|---|---:|---|
| `ineligible` | 422 | Server readiness/eligibility check failed; `details` carries blocker codes. |
| `conflict` | 409 | Scheduling conflict, duplicate idempotency key with different payload, or uniqueness conflict. |
| `forbidden` | 401, 403 | Actor is unauthenticated (401) or authenticated but lacks role/scope/ownership (403). |
| `invalid_state` | 409 | Requested transition is not legal from current state. |
| `validation_error` | 422 | Malformed body, invalid field, or invalid interval shape. |
| `not_found` | 404 | Entity does not exist or is not visible to actor. |

Framework validation errors must be normalized to `validation_error`. Do not reveal whether an out-of-scope private object exists.

### Endpoints

| Method and path | Auth / role | Request JSON | Response JSON | Statuses |
|---|---|---|---|---|
| `GET /api/auth/demo-accounts` | Anonymous | None | `{"accounts":[{"id":"uuid","display_name":"Requester A","role":"requester"}]}`; returns seeded account buttons only, never hashes. | 200 |
| `POST /api/auth/demo-login` | Anonymous; controlled demo account only | `{"account_id":"uuid","password":"<shared visible demo password>"}` | `{"user":{"id":"uuid","display_name":"...","role":"...","organization_id":"...","is_demo":true}}`; sets a signed HttpOnly session cookie. Password is verified against the selected User's hash. | 200, 401, 422 |
| `GET /api/auth/session` | Authenticated | None | `{"user":{"id":"uuid","display_name":"...","role":"...","organization_id":"...","is_demo":true}}` | 200, 401 |
| `POST /api/auth/logout` | Authenticated | None | `{"ok":true}` | 200, 401 |
| `GET /api/resources?query=&category=&available_from=&available_to=` | Authenticated | Query parameters | `{"items":[{"id":"uuid","name":"...","category":"...","capability_tags":[],"location":"...","status":"active","readiness":{"ready":true,"blockers":[]},"availability":[]}],"total":0}` | 200, 401, 422 |
| `POST /api/resources` | Lab manager or admin within scope | `{"name":"...","category":"...","capability_tags":[],"location":"...","status":"active","hold_review_date":null,"weekly_operating_hours":[{"weekday":1,"start":"09:00","end":"17:00"}],"max_duration_minutes":null,"exclusive_booking":true}` | `{"resource":{...}}` | 201, 401, 403, 422 |
| `GET /api/resources/{id}` | Authenticated | None | `{"resource":{...},"active_policy":{...},"readiness":{"ready":true,"blockers":[]},"availability":[]}` | 200, 401, 404 |
| `PATCH /api/resources/{id}` | Scoped manager or admin | Partial mutable resource fields; no `owner_id`, actor, or organization override. | `{"resource":{...}}` | 200, 401, 403, 404, 422 |
| `POST /api/resources/{id}/policy-drafts` | Scoped manager or admin | `{"structured_requirements":{"training_codes":[],"supervisor_required":false,"supervised_windows":[]},"allowed_uses":["project","coursework","research"],"priority_policy":{}}`; editing creates a new version. Human-authored structured draft only. | `{"policy":{"id":"uuid","resource_id":"uuid","version":1,"effective_at":null,"approved_by":null,...}}` | 201, 401, 403, 404, 422 |
| `POST /api/resources/{id}/policies/{version}/activate` | Scoped lab manager only | `{"reason":"..."}` | `{"policy":{...,"approved_by":"uuid","activation_reason":"..."},"audit_event_id":"uuid"}` | 200, 401, 403, 404, 409, 422 |
| `POST /api/training-records` | Scoped lab manager | `{"user_id":"uuid","requirement_code":"...","status":"valid","valid_from":"...","valid_to":null}`; verifier is derived from session. | `{"training_record":{...}}` | 201, 401, 403, 404, 422 |
| `POST /api/requests` | Requester | `{"resource_id":"uuid","purpose":"...","start_at":"...","end_at":"..."}` plus optional `Idempotency-Key` header; requester ID is derived. Creates DRAFT and submits it in one transaction. | `{"request":{"id":"uuid","status":"PENDING_REVIEW|INELIGIBLE","created_at":"..."},"eligibility":{"eligible":true,"blockers":[]} }`. If ineligible, persist `INELIGIBLE`, return 201 with `eligible:false` and all blockers; do not imply a booking exists. | 201, 401, 404, 409, 422 |
| `GET /api/requests/mine` | Requester | Optional `status`, `from`, `to` query filters | `{"items":[{"request":{...},"decision":{...},"booking":{...},"access_contract":{...}}],"total":0}` | 200, 401, 422 |
| `GET /api/manager/requests` | Scoped lab manager | Optional resource/status/date filters | `{"items":[{"request":{...},"eligibility":{...},"allocation_recommendation":{...}}],"total":0}` | 200, 401, 403, 422 |
| `POST /api/requests/{id}/decision` | Scoped manager; cannot be requester | `{"outcome":"approved|rejected|waitlisted","reason":"...","override_reason":null}`; policy/input snapshot is computed by server. | `{"decision":{...},"request":{"id":"uuid","status":"..."},"booking":{...},"access_contract":{...}}` | 200, 401, 403, 404, 409, 422 |
| `POST /api/bookings/{id}/check-in` | Booking requester | `{"checklist_version":"...","condition":{"physical_condition":"ok","accessories_complete":"yes","functional_test":"works","notes":null},"evidence_references":[{"file_name":"...","note":"..."}]}` plus optional `Idempotency-Key`. | `{"booking":{"id":"uuid","status":"CHECKED_IN"},"handover_report":{...}}` | 200, 401, 403, 404, 409, 422 |
| `POST /api/bookings/{id}/check-out` | Booking requester | Same checklist schema and metadata-only evidence as check-in, plus optional `Idempotency-Key`. | `{"booking":{"id":"uuid","status":"CLOSED|INCIDENT_REVIEW"},"handover_report":{...},"incident":null}` | 200, 401, 403, 404, 409, 422 |
| `POST /api/bookings/{id}/extension-requests` | Not available | Extensions are not in this build. | Not served; do not return success-shaped data. | N/A |
| `POST /api/bookings/{id}/incidents` | Booking requester or scoped manager | `{"category":"...","description":"..."}`; reporter derived from session. | `{"incident":{...}}` | 201, 401, 403, 404, 409, 422 |
| `GET /api/incidents/{id}` | Reporter/requester or scoped manager; auditor read-only for demo | None | `{"incident":{...},"booking":{...}}` | 200, 401, 403, 404 |
| `POST /api/incidents/{id}/responses` | Reporter/requester or scoped manager | `{"message":"..."}`; actor/time derived. | `{"incident":{...}}` | 201, 401, 403, 404, 409, 422 |
| `POST /api/incidents/{id}/resolve` | Scoped lab manager | `{"outcome":"resolved|dismissed","rationale":"..."}` | `{"incident":{...},"audit_event_id":"uuid"}` | 200, 401, 403, 404, 409, 422 |
| `GET /api/resources/{id}/timeline` | Authenticated; auditor read-only | Optional `from`, `to` | `{"items":[{"timestamp":"...","event":"...","actor":"...","summary":{...}}]}` | 200, 401, 404, 422 |
| `GET /api/resources/{id}/memory` | Authenticated; auditor read-only | Optional `from`, `to`; defaults to the last 30 days | `{"range":{"from":"...","to":"..."},"metrics":{...},"recommendations":[...],"demo_data":true}` | 200, 401, 404, 422 |
| `GET /api/audit?entity_type=&entity_id=` | Admin, scoped manager, or auditor read-only; requester own related events only | Query filters | `{"items":[{"id":"uuid","actor_id":"uuid","entity_type":"...","entity_id":"uuid","action":"...","timestamp":"...","before_summary":{},"after_summary":{}}]}` | 200, 401, 403, 422 |
| `POST /api/ai/match` | Authenticated requester/manager/admin | `{"goal":"...","constraints":{"categories":[],"capabilities":[],"available_from":null,"available_to":null}}` | `{"criteria":{"categories":[],"capabilities":[]},"candidates":[{"resource_id":"uuid","explanation":"..."}],"source":"deterministic|ai|deterministic_fallback","disclosure":"Suggestions only; backend eligibility and booking rules still apply."}` | 200, 401, 422; deterministic keyword matching runs first; optional model has an 8-second timeout; timeout/invalid output returns deterministic result |
| `POST /api/ai/summarize-incident` | **Excluded by fixed AI scope; no route** | Not accepted | Not served; incident summaries remain human-written. | N/A |
| `GET /api/notifications` | Authenticated | Optional `unread_only` | `{"items":[{"id":"uuid","type":"...","related_entity_type":"...","related_entity_id":"uuid","read_at":null,"created_at":"..."}]}` | 200, 401, 422 |
| `POST /api/notifications/{id}/read` | Recipient only | None | `{"notification":{...}}` | 200, 401, 403, 404 |
| `POST /api/admin/demo-reset` | Institution admin and restricted demo environment | `{"confirmation":"RESET_DEMO_DATA"}` | `{"ok":true,"reset_counts":{"resources":0,"requests":0,"bookings":0,"incidents":0}}` | 200, 401, 403, 422, 500 |

The pack's endpoint list is covered above. Extension requests and AI incident summaries are explicitly non-routes in this fixed build; do not implement placeholders. The demo-login page presents an account button per seeded account and one visible shared password; the password is hashed per User row, and session state is carried in a signed HttpOnly cookie using `SECRET_KEY` from the environment. The `ineligible` error code applies when a requested transition is blocked on a recheck; initial submission instead persists `INELIGIBLE` and returns the blocker details as described above. Repeated decision submissions must be idempotent only when the same request, outcome, and reason are repeated; a different second decision returns `invalid_state`. Check-in/out retries with the same idempotency key and same payload return the original persisted result; same key/different payload returns `conflict`. Without a key, unique `(booking_id, stage)` still prevents duplicate reports.

## 12. SECURITY AND PRIVACY MINIMUMS

- Enforce server-side authorization on every protected endpoint; UI visibility is not security.
- Derive user ID, role, and scope from the authenticated demo user, never from request JSON.
- Perform object-level ownership and organization-scope checks for resources, requests, bookings, incidents, and evidence references.
- Validate all inputs with Pydantic and database constraints; use ORM/parameterized operations.
- Keep secrets only in environment variables; never expose provider keys to the browser. Existing `.env.example` contains placeholder names only.
- Store `SECRET_KEY` in the server environment and use it to sign the HttpOnly demo-session cookie; never put it in frontend configuration.
- Store only a password hash in each User row. The shared demo password is intentionally visible on the demo login page and is not a production credential.
- Restrict demo reset to the institution-admin role and a server-side demo environment; reset only records marked `is_demo`, never ordinary/non-demo data.
- Use synthetic Northstar data only; no real student IDs, sensitive training documents, or real identity data.
- Keep audit and AI logs minimal; do not log secrets or unnecessary personal content.
- Keep evidence private; do not serialize public evidence URLs or permit cross-user access.
- Send an AI provider only the minimum resource-matching text/constraints needed; never send secrets, identity credentials, or incident content.
- Treat provider output as untrusted; apply schema validation, timeout, candidate-ID allowlisting, and deterministic fallback.
- Use transactions/constraints for conflicting booking decisions. Audit events cannot be updated/deleted through the API.

## 13. AI FEATURE (OPTIONAL, P1)

Resource matching is the only permitted user-facing AI capability. It may convert the user's project goal/constraints into structured search criteria and rank resources returned by deterministic filters. It must not decide eligibility or perform any booking action.

**Input JSON**

```json
{
  "goal": "string, required, bounded length",
  "constraints": {
    "categories": ["string"],
    "capabilities": ["string"],
    "available_from": "UTC timestamp or null",
    "available_to": "UTC timestamp or null"
  }
}
```

The pack does not set maximum text/array lengths; enforce ordinary API validation and record exact limits as an implementation question before exposing the endpoint.

**Output JSON schema**

```json
{
  "criteria": {
    "categories": ["string"],
    "capabilities": ["string"]
  },
  "candidates": [
    {"resource_id": "UUID", "explanation": "string"}
  ]
}
```

Validation rules:

1. Parse JSON and validate exact fields/types; reject extra decision/action fields.
2. Bound candidate count to the filtered result set; deduplicate resource IDs.
3. Every candidate ID must already exist in the deterministic result set for the authenticated scope and query. If the output contains any unknown/hallucinated ID, discard the untrusted ranking and return deterministic results.
4. Re-run backend readiness, eligibility, availability, maintenance, and policy checks when the user opens a resource or submits a request.
5. Do not use the output to grant access, waive training, clear holds, approve/waitlist, assign blame, or impose a penalty.
6. Disclose whether results came from AI or fallback; never claim an AI call happened when it did not.

Deterministic keyword/category matching runs first and is the normal fallback. A provider/model may optionally rerank/clarify matching after deterministic search; enforce an 8-second timeout. Timeout, malformed output, or unknown resource IDs returns the deterministic results without breaking any core workflow. Disclose the source (`deterministic`, `ai`, or `deterministic_fallback`); never imply that the model ran when it did not. Provider/model and maximum input/output size remain implementation choices; no provider is required for the build.

## 14. FOLDER STRUCTURE

The structure below follows the build pack. Responsibilities are descriptions, not permission to create extra modules beyond implementation needs.

### Backend

```text
app/
  main.py
  api/
    auth.py
    resources.py
    requests.py
    bookings.py
    handover.py
    incidents.py
    audit.py
    analytics.py
    ai.py
  domain/
    eligibility.py
    allocation.py
    state_transitions.py
    readiness.py
    capacity_insights.py
  models/
  schemas/
  services/
    audit_service.py
    contract_service.py
    evidence_service.py
    notification_service.py
    ai_provider.py
  tests/
```

| Module | Responsibility |
|---|---|
| `main.py` | FastAPI application composition, startup, and router registration. |
| `api/auth.py` | Seeded account list, account-button demo login, signed HttpOnly session cookie, and logout/current-session routes. |
| `api/resources.py` | Resource CRUD, policy versions, resource timeline, and resource memory routing. |
| `api/requests.py` | Request submission, requester history, manager queue, and decision routing. |
| `api/bookings.py` | Booking check-in/out, cancellation cutoff, and no-show state; no extension endpoint. |
| `api/handover.py` | Handover/checklist request and response schemas/routes. |
| `api/incidents.py` | Incident retrieval, responses, and authorized resolution. |
| `api/audit.py` | Read-only audit query routes. |
| `api/analytics.py` | Persisted Resource Memory metrics and recommendations. |
| `api/ai.py` | Optional resource matching only; no policy drafting or incident summarization. |
| `domain/eligibility.py` | Authoritative eligibility evaluation. |
| `domain/allocation.py` | Deterministic ranking and decision snapshots. |
| `domain/state_transitions.py` | Central legal transition rules. |
| `domain/readiness.py` | Resource readiness and ordered blockers. |
| `domain/capacity_insights.py` | Deterministic, source-linked recommendations. |
| `models/` | SQLAlchemy persistence entities and constraints. |
| `schemas/` | Pydantic API and structured-data schemas. |
| `services/audit_service.py` | Atomic server-side audit event creation. |
| `services/contract_service.py` | Immutable Access Contract snapshots/version handling. |
| `services/evidence_service.py` | Validate evidence metadata (`file_name`, `note`); no binary storage/upload. |
| `services/notification_service.py` | In-app notification creation and read state. |
| `services/ai_provider.py` | Provider adapter, timeout, strict validation, and fallback. |
| `tests/` | pytest domain, API authorization, transition, persistence, and regression tests. |

### Frontend

```text
src/
  app/
  routes/
  components/
  features/
    discovery/
    resource-detail/
    requests/
    manager-queue/
    access-contract/
    handover/
    incidents/
    resource-memory/
    admin/
  api/
  types/
  tests/
```

| Module | Responsibility |
|---|---|
| `app/` | Application shell, providers, and shared app initialization. |
| `routes/` | Route composition and role-aware page routing; not authorization enforcement. |
| `components/` | Reusable accessible presentation components. |
| `features/discovery/` | Resource search, filters, and optional matching suggestions. |
| `features/resource-detail/` | Resource, readiness, blockers, policy, and availability display. |
| `features/requests/` | Requester submission, status, and explanation views. |
| `features/manager-queue/` | Manager review queue and human decision actions. |
| `features/access-contract/` | Versioned session-conditions snapshot display. |
| `features/handover/` | Check-in/check-out condition checklist and evidence metadata UI. |
| `features/incidents/` | Neutral incident report, response, and review screens. |
| `features/resource-memory/` | Persisted metrics and evidence-backed recommendations with demo labels. |
| `features/admin/` | Restricted demo administration/reset UI. |
| `api/` | Typed backend client and normalized error handling. |
| `types/` | Types aligned with Pydantic/OpenAPI schemas. |
| `tests/` | Frontend smoke tests for real API-backed journeys and visible states. |

## 15. DEMO SCENARIO AND SEED DATA

All seed rows are synthetic and `is_demo=true`. Every seeded statistic, history item, contract, audit event, and recommendation is labelled **DEMO DATA — not live institutional statistics**.

### Seed accounts

The build pack specifies these account labels/roles but supplies no password value. These labels are the exact seed identities; the login flow uses the one visible shared demo password defined in Section 18, and its literal value must be provided on the landing page/README before the judge run.

| Demo account label | Role | Seed purpose |
|---|---|---|
| Requester A | Requester | Eligible clean-lifecycle user. |
| Requester B | Requester | Competing eligible requester with low recent usage. |
| Requester C | Requester | Missing-training blocker scenario. |
| Lab Manager | Resource owner / lab manager | Verifies training, reviews allocation, handles handover/incident. |
| Institution Admin | Institution admin | Restricted reset, role/resource/policy administration, audit review. |
| Judge Auditor | Judge / read-only auditor | Inspects demo decisions, evidence metadata, and event history without writes. |

This is six synthetic accounts, within the pack's 4-6 range. Admin/Auditor are separate because the fixed permission model defines four roles.

### Seed resources

The pack supplies these six resource examples (the lower bound of 6-8). All six use deterministic UUIDs defined in the seed script and set `exclusive_booking=true`. Weekly operating hours are stored per resource as JSON entries `{weekday,start,end}` in Asia/Kolkata local time. Exact IDs, room locations, capability details, policy training codes, and hours are assigned by the seed script.

| Resource | Seed condition |
|---|---|
| 3D printer | Active; exclusive. |
| Camera kit | Active; exclusive. |
| Oscilloscope training station | Active; exclusive; has a training prerequisite for the missing-training scenario. |
| Electronics bench | Active; exclusive. |
| Meeting/project room | Active; exclusive. |
| Maintenance-hold resource | One of the five named resources is set to `maintenance_hold` with `hold_review_date`; it remains unavailable until an authorized manager changes status. Exact resource is selected by seed script. |

### Training and lifecycle seed records

| Seed record | Required behavior |
|---|---|
| Requester A training | One verified, currently valid TrainingRecord matching the clean-lifecycle resource's policy requirement. |
| Requester B training | One verified, currently valid record matching the competing request's policy requirement so the request is eligible. |
| Requester C training | No valid record for the oscilloscope training-station prerequisite; submission must return `missing_training`. |
| Completed booking | One closed booking with both IN and OUT reports, used to demonstrate completed hours. |
| Pending request | One eligible request in `PENDING_REVIEW`. |
| Competing request | A second eligible request for the same constrained resource/overlapping slot, allowing deterministic allocation comparison before confirmation. |
| Waitlisted request | One eligible request in `WAITLISTED`, with persisted policy reason. |
| Upcoming booking | One confirmed, future booking that contributes to scheduled hours. |
| Incident | One synthetic condition discrepancy linked to a booking, in human review, with no blame attribution or penalty. |

### Judge journey

1. Sign in with the visible Requester C demo credentials; discover the oscilloscope training station.
2. Attempt a request and observe the backend `missing_training` blocker and authorized next action.
3. Sign in as Requester A (or have the lab manager verify training for the scenario); discover a suitable resource and inspect policy/readiness.
4. Submit the eligible request. Inspect the pre-seeded competing eligible request and deterministic policy explanation.
5. Sign in as Lab Manager; review eligibility and competing demand, record a reason, and approve or waitlist according to the pre-seeded allocation setup. Human decision is mandatory.
6. Open **Access Contract (session conditions)** and verify the approved interval, policy version, requirements, supervision, permitted use, and checklist version.
7. As the requester, complete check-in using the versioned checklist, then complete return using the same checklist. Verify persisted records after refresh and a closed booking.
8. Inspect resource timeline, audit events, and Resource Memory; verify values reconcile and show the DEMO DATA label.
9. Separately open the pre-seeded discrepancy incident, inspect responses/evidence metadata, and have the lab manager resolve or dismiss it with rationale. No blame or penalty is assigned.

The login page exposes a button per account and one visible shared demo password; the password value is set by the seed/release configuration and must be documented for judges. User/resource UUIDs are deterministic in the seed script. Exact requirement-code strings, interval timestamps, locations, and resource/request mapping are seed-script values; see Section 17. Display schedule times in IST and store instants in UTC.

## 16. BUILD ORDER AND GATES

The elapsed order follows the pack's 48-hour plan. Do not move to optional work while a preceding gate fails.

| Gate / elapsed target | Work | Required tests/evidence to pass |
|---|---|---|
| **G1: 2-8h - app boots and DB persists** | Modular monolith skeleton, SQLAlchemy `create_all`, deterministic seed script, demo auth, resource models, frontend shell/discovery. SQLite locally; PostgreSQL when deployed. No Alembic. | Backend and frontend boot; create/read/update resource persists after refresh/restart; `create_all` and seed succeed; account buttons authenticate with hashed shared password and server-derived roles. |
| **G2: 8-16h - eligibility, authorization, conflicts** | Readiness, training, maintenance, allocation decision, policy version, conflict prevention. | Missing/expired training blocked at submit/approval/check-in; maintenance blocks approval/check-in; unauthorized requester cannot approve; self-approval denied using a manager-owned request created directly in test setup; SQLite `BEGIN IMMEDIATE` and PostgreSQL resource-row `SELECT FOR UPDATE` tests prove overlapping concurrent confirmation cannot double-book; policy version and decision reason persist. |
| **G3: 16-24h - full lifecycle via UI/API** | Contract, check-in/out, condition reports, requester/manager flows. | Judge-equivalent UI/API journey from discovery through approval, immutable contract, check-in, checkout, and closed lifecycle; duplicate/out-of-window check-in/out denied; refresh retains records. |
| **G4: 16-24h - incidents and audit work** | Incident workflow, server-side audit events, private evidence references. | Discrepancy opens reviewable incident without blame; authorized manager can respond/resolve/dismiss; unauthorized role cannot; each critical transition has audit event; audit history has no update/delete API. |
| **G5: 30-35h - AI failure does not break core** | Optional resource matching only, strict schema, timeout and deterministic fallback. | Matching output validates; unknown resource IDs/malformed output/timeouts use deterministic results; core request/booking remains available when provider is unavailable; AI cannot invoke a decision transition. If no stable AI integration, ship deterministic matching and disclose fallback. |
| **G6: 35-40h - deployed version passes smoke tests** | Deploy one judge-accessible host with persistent DB; adversarial/usability checks. | Fresh-session login; resource and booking data survive refresh/restart as expected; clean lifecycle and incident path smoke tests pass on deployed build; no P0 access/control/conflict/persistence defect; usable laptop/mobile viewport. |
| **G7: 40-48h - submission artifacts complete** | Independent judge run, regression, README, architecture, test notes, AI disclosure, credentials and submission materials. | Full regression rerun on final deployed version; every README credential/link works; truthful feature/test status; demo data clearly labelled; no secrets/real data; required repository, PDF/forms, team contributions, and links verified. |

If a P0 workflow fails, stop P2/polish work and repair it. If the core flow is unstable by hour 30, cut optional AI/analytics expansion. If deployment is unstable at hour 35, simplify deployment rather than adding integrations. A release gate passes only with recorded evidence, not an agent assertion.

## 17. OPEN QUESTIONS AND RISKS

Section 18 resolves the contract decisions listed in this section's original build. The following implementation details remain open; they must be fixed in the seed/release configuration without changing the product rules in this contract.

| # | Remaining open question / risk | Blocks or affects |
|---:|---|---|
| 1 | What literal shared demo password is selected for the visible login page? It must be deliberately public/demo-only, hashed in every User row, and never reused as a secret. | Seed script, judge login, README. |
| 2 | What exact weekly hours, room locations, capability tags, hold review date, policy training codes, and scenario timestamps/map are assigned to the six resources and seeded requests? | Deterministic seed content and judge scenario. |
| 3 | What are the exact TrainingRecord status values and validity/expiry policy for `valid_to=null`, and which exact training code strings are used in seed data? | Training validation and seed script. |
| 4 | Which booking states contribute to the 10-hour booked-usage total, and how are durations clipped at the 30-day window boundaries? | Exact usage-limit accounting and allocation tests. |
| 5 | What are the maximum accepted lengths/counts for matching input, checklist notes, incident descriptions, and evidence metadata? | Pydantic limits and validation tests. |
| 6 | What exact cookie lifetime and CSRF protection mechanism are used with the signed HttpOnly session cookie? | Auth/session hardening. |
| 7 | Which optional model/provider, if any, is used for resource matching? Deterministic matching must work with no provider configured. | Optional AI adapter only. |
| 8 | What is the final migration/initialization recovery approach if `create_all` cannot reconcile an existing deployed schema? Alembic is explicitly not used in this build. | Deployment recovery; do not silently drop persisted data. |

Recommendation recurrence thresholds in Section 10 are the explicit initial interpretation (`2` qualifying users/requests); change them only through a documented contract decision. No other open issue may weaken authorization, eligibility, conflict safety, auditability, or the AI boundary.

**Risks:** SQLite and PostgreSQL use different transaction-locking mechanics; the specified locking paths must be concurrency-tested. Weekly operating and supervised windows must be interpreted consistently in IST and converted to UTC across date boundaries. Metadata-only evidence does not upload or preserve image contents. Do not advertise excluded AI capabilities as implemented.

## 18. DECISIONS ADDENDUM

This addendum resolves the relevant Section 17 questions and supersedes any inconsistent earlier text. Implementation values not specified here remain listed in Section 17.

### 18.1 Authentication and roles

- The demo login page shows one button for each seeded account and one visible shared demo password.
- Store a password hash (not plaintext) in `User.password_hash`; verify the entered shared password against the selected account's hash.
- On successful login, issue a signed session in an HttpOnly cookie. The signing `SECRET_KEY` comes only from the server environment.
- Institution Admin and Judge Auditor are separate accounts with separate roles. The six demo accounts remain Requesters A/B/C, Lab Manager, Institution Admin, and Judge Auditor.
- The literal public demo password is a seed/release value and remains an implementation detail in Section 17; never commit production secrets.

### 18.2 Resources, availability, and policies

- All six seeded resources are exclusive (`exclusive_booking=true`).
- Resource availability is `weekly_operating_hours`: JSON entries `{weekday,start,end}`, with ISO weekday 1-7 and local `HH:MM` values. Interpret weekly hours in Asia/Kolkata, store requested instants in UTC, and display schedule times in Asia/Kolkata (IST).
- Supervisor coverage is stored in each `ResourcePolicy.structured_requirements.supervised_windows`; do not add a supervisor-coverage table.
- The exact policy schema is:

  ```json
  {
    "structured_requirements": {
      "training_codes": [],
      "supervisor_required": false,
      "supervised_windows": []
    },
    "allowed_uses": ["project", "coursework", "research"],
    "priority_policy": {}
  }
  ```

- Each `supervised_windows` entry has `{weekday,start,end}` in the same weekly IST format. `allowed_uses` contains only the listed values.
- Editing policy creates a new version. Only a scoped lab manager activates a version, and activation requires a reason stored with the version and emitted in audit. Policy edits do not mutate old versions or Access Contracts.
- Maintenance hold is represented by `Resource.status=maintenance_hold` and `Resource.hold_review_date`. Passing the review date creates a recommendation only; it never clears the hold automatically.
- The seed script records the initial maintenance-hold status event so Resource Memory can calculate seeded blocked hours from audit history.

### 18.3 Allocation and time rules

- Store timestamps/instants in UTC and display them in Asia/Kolkata (IST). Booking intervals are half-open `[start_at,end_at)`.
- Allocation uses a rolling 30-day usage window. A newcomer has zero completed bookings for that resource in the window. Enforce a limit of 10 booked hours per user per resource in the window.
- There are no priority tiers. Prefer newcomers, then lower booked hours, then earlier request creation time. If contenders remain tied, the manager chooses and records a reason. The manager may override the usage limit only with an audit reason. `priority_policy` remains `{}`.
- Only confirmed bookings block overlap at eligibility/ranking time. Approval rechecks confirmed bookings under a lock/transaction; competing unconfirmed requests cannot both become overlapping confirmed bookings.
- Check-in is permitted from 15 minutes before booking start up to, but not including, booking end. If no check-in exists 30 minutes after start, the server records the `NO_SHOW` state/event; if the user checks in later but before booking end, allow `NO_SHOW -> CHECKED_IN` and retain the no-show event in history and metrics. This reconciles the 30-minute threshold with the check-in window closing at booking end.
- Cancellation is permitted no later than 2 hours before start. A waitlisted request expires at its slot's start time.
- Extensions are not in this build and have no endpoint.
- Cancellation metrics count only requests canceled after approval. No-show metrics count the immutable `booking.no_show` event at the 30-minute threshold, including when a late check-in later occurs before booking end.

### 18.4 Handover, incidents, contracts, and notifications

- Check-in and check-out use one versioned checklist with exactly these fields and values:
  - `physical_condition`: `ok`, `minor_wear`, or `damaged`
  - `accessories_complete`: `yes` or `no`
  - `functional_test`: `works` or `issue`
  - `notes`: text or null
- An OUT discrepancy exists if physical condition is worse than IN (`ok < minor_wear < damaged`), accessories are incomplete (`no`), or functional test is `issue`. Create a reviewable incident; do not infer blame or impose a penalty.
- Incident categories are `damage`, `missing_part`, `malfunction`, `late_return`, and `other`.
- Evidence is metadata only: `file_name` and `note`; no binary upload, MIME type, file size, public URL, or file storage is part of this build.
- Access Contract status is `ACTIVE`, `COMPLETED`, or `CANCELLED`; expiry is booking `end_at`. A no-show at +30 minutes does not cancel the contract before the check-in window closes; if no later check-in occurs by booking end, mark the contract `CANCELLED`. Amendments are not supported. Re-approval creates a new contract version while preserving old versions.
- Create in-app notifications for decisions, waitlist promotion, and cancellation. When the notifications list is read during the check-in window (from 15 minutes before start up to, but not including, end), create/return one deduplicated `checkin_due` notification for that booking.
- Compute overdue-return notices on read when current time is after booking end and no checkout exists; do not depend on an external scheduler. Persist standard notification recipient/type/related entity/created/read timestamps; an overdue notice may be returned as a deduplicated read-time derived notice without a stored row.

### 18.5 Resource Memory and recommendations

- Resource Memory defaults to the last 30 days when `from`/`to` are omitted.
- Selected recommendations are: training backlog, supervised-slot shortage, and overdue maintenance-hold review. Use Section 10's source counts/date-range format and safe text.
- For deterministic initial thresholds, training backlog means at least two distinct users blocked by one training code; supervised-slot shortage means at least two eligible requests blocked solely by supervised-window coverage. A maintenance recommendation triggers when `hold_review_date` is before the current date. These thresholds are an explicit initial interpretation of “multiple”/“repeated” in the pack.
- Label every seeded metric and recommendation **DEMO DATA — not live institutional statistics**.

### 18.6 AI, persistence, and conflict safety

- Run deterministic keyword/category matching first. An optional model may assist resource matching only; use an 8-second timeout and the disclosed deterministic fallback. No provider is required for core operation.
- SQLite is the local database. Use PostgreSQL when deployed.
- Initialize schema with SQLAlchemy `create_all` and populate it with a seed script; do not add Alembic.
- Conflict safety is transaction plus overlap check: acquire `BEGIN IMMEDIATE` before the overlap query on SQLite; lock the resource row with `SELECT FOR UPDATE` before the overlap query on PostgreSQL. Commit booking and audit event atomically.
- Seed UUIDs are deterministic and are defined in the seed script. User rows store `id`, `display_name`, `role`, `organization_id`, `is_demo`, and `password_hash` (plus only fields strictly required by the existing entity contract).
- Self-approval verification creates a manager's own request directly in test setup, not through the request API. The manager's decision must be forbidden.

### Edits made in this addendum

The following earlier sections were updated to apply these decisions:

1. **Document preamble and Section 17:** recorded the fixed stack, made Section 18 authoritative, and replaced resolved questions with the remaining implementation details and risks.
2. **Section 2 (Roles and Permission Matrix):** limited policy activation to the scoped lab manager with a reason; preserved admin/auditor as separate roles.
3. **Section 3 (Data Model):** added hashed demo password; deterministic user IDs; resource weekly availability and maintenance review date; fixed exclusivity; exact policy schema and activation reason; contract statuses/expiry/versioning; exact checklist/evidence metadata and incident categories.
4. **Section 4 (State Machines):** separated request from booking lifecycle; added exact check-in/cancellation/waitlist-expiry/no-show transitions, late check-in after the no-show event but before booking end, and illegal-transition rules.
5. **Section 5 (Invariants):** specified SQLite/PostgreSQL conflict locks and direct test setup for manager self-approval.
6. **Sections 6-7 (Readiness and Allocation):** sourced supervisor coverage from policy windows and fixed the 30-day, 10-hour, newcomer, usage, tie, and manager-override rules.
7. **Sections 8-10 (Contract, Handover, Resource Memory):** fixed contract status/expiry/no-amendment behavior, checklist discrepancy/category mapping, metadata-only evidence, metrics definitions, audit-derived maintenance intervals, default range, and recommendation rules.
8. **Section 11 (API):** specified account-button login, shared-password request, cookie session, resource/policy schemas, manager-only activation, checklist payloads, extension omission, memory defaults, and matching timeout/fallback.
9. **Section 12 (Security):** added environment-only cookie signing key and hashed shared demo-password requirements.
10. **Section 13 (AI):** set deterministic-first matching and the optional 8-second model timeout/fallback.
11. **Section 14 (Folder Structure):** clarified authentication, booking, and evidence module responsibilities without changing the pack's folder tree.
12. **Section 15 (Demo Scenario):** separated admin/auditor accounts, made all six resources exclusive, specified weekly hours/timezone and deterministic seed UUIDs.
13. **Section 16 (Build Order and Gates):** specified `create_all` plus seed script/no Alembic and database-specific concurrency tests.
