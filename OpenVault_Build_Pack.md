**OPENVAULT**

**CODEVERSE INDIA • TEAM BUILD PACK**

*From idle resources to verified, usable capacity*

| **DOCUMENT PURPOSE** | **STATUS** |
| --- | --- |
| Shared product definition, build plan, acceptance criteria, AI-agent prompts, judge checklist and submission controls. | Pre-build planning document. The actual product implementation must begin during the official build window. |

Version: 1.0 | Prepared: 30 October 2026 | Product name is provisional; check name/domain availability before public use.

Important: This is a planning/specification artifact, not a claim that any product code, integration, test, deployment or user research has already been completed.

# 1. Executive decision

Recommendation: build OpenVault as a focused resource-access operations system for one engineering-college laboratory or makerspace—not as a generic equipment marketplace.

Core thesis: institutions do not merely need to know whether an asset is free. They need to know whether it is actually ready and authorised to be shared, what is blocking access, who can resolve the blocker, and whether the resulting session completed safely and fairly.

## The differentiating loop

RESOURCE DISCOVERED

      ↓

READINESS / BLOCKER CHECK

      ↓

ELIGIBILITY + AVAILABILITY + SUPERVISION

      ↓

EXPLAINABLE ALLOCATION

      ↓

VERSIONED ACCESS CONTRACT

      ↓

CHECK-IN + CONDITION EVIDENCE

      ↓

RETURN / INCIDENT / HUMAN REVIEW

      ↓

AUDITABLE RESOURCE MEMORY

      ↓

CAPACITY-RECOVERY RECOMMENDATION

      ↓

AUTHORIZED ACTION + MEASURED RESULT

The competitive bet is not that each individual feature is unprecedented. The bet is that we integrate readiness blockers, proof-carrying access, fair allocation, evidence-backed handover and capacity recovery into one small workflow that works end to end.

## What we must not claim

Do not claim there are no competitors or that no existing platform has similar features.

Do not claim a percentage increase in utilisation unless it is measured in a real pilot.

Do not present seeded or simulated metrics as live institutional data. Label demonstration data clearly.

Do not describe a hash-linked audit log as blockchain, immutable proof or legal proof.

Do not let AI make binding safety, access, penalty, liability or damage decisions.

Do not overbuild multi-institution federation, payments, IoT, biometrics or autonomous approvals in 48 hours.

# 2. Research and judging implications

The official CodeVerse India page (checked 30 October 2026) describes a 48-hour build, requires a judge-accessible working product and repository, and says the judge should complete the main journey without being talked through it. Its published criteria are: problem understanding 20, solution and whether it runs 25, technical depth/reliability 20, originality 15, usability/real-world fit 12, documentation/future 8.

The supplied challenge brief has a different 100-point rubric. Until the organiser confirms which rubric governs this particular submission, design to satisfy both rather than optimising for only one.

No verifiable public archive of previous winners for this exact CodeVerse event was found during this research. Therefore this pack does not invent past-winner tactics. Use the published rules and judging criteria as evidence; treat all competitor assumptions as hypotheses.

## Competitive landscape: what this means

| **Existing category / example** | **Established baseline** | **Implication for OpenVault** |
| --- | --- | --- |
| I-STEM (India's public research-infrastructure sharing initiative) | Discovery and booking of institutional scientific facilities; broad national scope. | Do not pitch only a national equipment directory. Focus on local operational readiness, conditional access, evidence handover and capacity recovery. |
| Lab/core-facility booking software | Scheduling, approval, training/access gates, no-show rules and utilisation reporting are established product features. | Booking + eligibility + analytics alone is not unique. |
| Makerspace operations tools | Training prerequisites, equipment booking, check-in/return and maintenance workflows are familiar. | Show a connected blocker-to-resolution loop and auditable access lifecycle, not a feature checklist. |
| Equipment rental / peer-sharing services | Identity verification, condition checklists and reservation controls exist in the market. | Do not claim that verification or before/after photos alone are novel. |

Research sources are listed at the end. These sources establish the competitive baseline; they do not prove that OpenVault is unique or that the proposed unmet need is universal.

# 3. Product scope and target setting

## Initial user and setting

Target one engineering-college makerspace/lab that lends low-to-moderate-risk project resources under staff oversight. Use a fictional institution and synthetic accounts for the hackathon demo. Use ordinary demonstration resources such as a 3D printer, camera kit, oscilloscope training station or electronics bench. Do not facilitate unsupervised access to hazardous equipment.

## Roles

| **Role** | **Allowed actions** |
| --- | --- |
| Requester / student team | Discover resources; inspect requirements; request a slot; see eligibility blockers; complete check-in/out forms; report an issue; view own request history. |
| Resource owner / lab manager | Create/edit resources and policies; approve/reject/waitlist requests; record authorised training sign-offs; perform handover review; handle incidents. |
| Institution admin | Manage roles, policy templates, resource status, audit review and demo data; cannot silently rewrite past events. |
| Judge / read-only auditor | Use provided demo roles and inspect decisions, evidence metadata and event history without changing production state. |

## Primary user story

A student team needs a resource for a project. OpenVault finds suitable resources, explains any access blocker, allows a valid request, handles competition for a scarce slot, obtains human approval, issues a versioned Access Contract, records handover and return, routes any incident to human review, and updates resource capacity insights.

## Explicitly out of scope

A public cross-campus marketplace or national network in the hackathon build.

Payments, deposits, fines or automated penalties.

Real institutional identity verification or integration without permission.

Biometric identity, face recognition, live hardware control or IoT claims.

AI-based guilt, damage attribution, liability or disciplinary decisions.

Unverified claims about money saved, utilisation increased or incidents prevented.

Large multi-agent runtime in the deployed product. Multi-agent AI is for the development workflow; user-facing AI stays narrow.

# 4. The product's five connected capabilities

## 4.1 Readiness and blocker resolution

Each resource has a shareability/readiness status computed from explicit fields: active/maintenance status, owner approval, required training, supervision availability, permitted use, booking availability and any policy-defined prerequisite. The system should show exact blockers and the authorised next action.

| **Example blocker** | **System behaviour** |
| --- | --- |
| Required training not recorded | Block booking; show the training requirement and a button to request/record training. Do not let AI waive it. |
| Maintenance hold active | Resource is not bookable; show the hold and expected review date if known. |
| Supervisor required but unavailable | Offer only slots with supervisor coverage or explain that no valid slot exists. |
| Policy missing/ambiguous | Mark resource as not ready for self-service; require owner to review the policy. |
| Slot conflict | Reject overlapping confirmation and explain alternatives/waitlist position. |

This is a stronger product insight than simply marking a resource Available/Unavailable: it makes the operational reason for idle capacity visible and actionable.

## 4.2 Proof-carrying Access Contract

On approval, create a snapshot of the exact approved conditions. The contract must retain policy version and booking details even if the resource policy later changes. Changes to an approved booking must create a new version or explicit amendment event; never silently mutate the old contract.

AccessContract {

  id, request_id, resource_id, requester_id, approver_id,

  start_at, end_at, approved_purpose,

  policy_version_id, requirements_snapshot,

  supervision_requirement, permitted_use,

  checkin_required, checkout_required,

  condition_checklist_version,

  status, created_at, approved_at, expires_at

}

The contract is an application record, not a legal contract unless legal review and institutional governance establish that status. Use the label “Access Contract (session conditions)” in the UI if needed to avoid implying legal enforceability.

## 4.3 Explainable fair allocation

Keep the initial allocation algorithm deterministic, small and testable. Apply hard constraints first, then a published institution-configurable policy for eligible competing requests.

Reject any request that violates access, training, maintenance, schedule or supervision constraints.

Protect already confirmed bookings; never approve overlapping reservations for the same exclusive resource.

Apply any explicit institutional priority rule only if it is documented and visible.

Among otherwise equivalent eligible requests, use recent usage or a rotating tie-breaker to discourage repeated monopolisation.

Record the inputs, policy version, outcome and human override reason. Show the requester a concise explanation.

Avoid presenting a single opaque “fairness score.” Usage history is only one signal and can disadvantage new users if poorly designed. The policy should include a newcomer/first-access path, configurable limits, and a human override with an audit reason.

## 4.4 Evidence-backed handover and incident handling

Check-in and check-out should use the same versioned checklist. Record timestamps, user, resource, structured condition choices, optional uploaded evidence and notes. Store file metadata and access permissions. Do not claim an image proves damage; it is evidence for human review.

Incident states: OPEN → INFORMATION_REQUESTED / UNDER_REVIEW → RESOLVED or DISMISSED. Capture reporter, event references, user response, owner response, reviewer and resolution rationale. No automatic fines or guilt decisions.

## 4.5 Capacity Recovery Loop

Resource Memory summarises actual persisted events: available hours, scheduled hours, completed hours, cancellations, no-shows, blocked hours by reason, waitlist demand, maintenance holds and unresolved incidents. Capacity recommendations must be rule-based and traceable to the underlying records.

| **Recommendation example** | **Required evidence** | **Safe output** |
| --- | --- | --- |
| “Add a supervised Saturday slot” | Repeated eligible requests denied solely because supervisor-covered hours are unavailable. | Suggestion with request count, date range and confidence/limitations. |
| “Resolve training backlog” | Several users blocked by the same missing training record. | Show affected eligible requests and the authorised training owner. |
| “Review maintenance hold” | Hold's review date has passed. | Create a review task; do not auto-release the resource. |
| “Consider another unit” | Repeated unmet demand after applying existing capacity and policy. | A planning signal, not a claim that a purchase is definitely needed. |

For a 48-hour prototype, implement 2–3 deterministic recommendations. Use AI only to summarise evidence in plain language, if time permits. Every recommendation must link to the source counts and date range. Seeded data must be labelled “demo data.”

# 5. Functional requirements and priority

| **Priority** | **Requirement** | **Acceptance evidence** |
| --- | --- | --- |
| P0 | Role-based demo login / controlled demo accounts | A requester cannot invoke manager/admin actions through API. |
| P0 | Resource CRUD with status, location, availability, policy and requirements | Create/edit a resource and see persisted changes after refresh. |
| P0 | Search/filter and resource detail | Search by capability/category; show eligibility, blockers and availability. |
| P0 | Eligibility/readiness engine | A blocked requester cannot receive an approved booking; exact reason returned. |
| P0 | Booking request + human approval/rejection/waitlist | Decision persists, has actor/reason/time and updates request status. |
| P0 | Conflict-safe scheduling | Concurrent/overlapping requests cannot both be confirmed for one exclusive resource. |
| P0 | Access Contract snapshot | Approved conditions and policy version remain inspectable. |
| P0 | Check-in/check-out + condition reports | Cannot check in without valid booking; cannot close twice; evidence metadata persists. |
| P0 | Incident workflow | Issue can be reported, reviewed, responded to and resolved by authorised staff. |
| P0 | Audit event timeline | Critical state changes create server-side events; user cannot edit history. |
| P0 | Resource Memory basic metrics | Counts derive from database records and show demo-data disclaimer. |
| P0 | Judge route, seeded data and reset instructions | A judge can complete the demo journey without developer intervention. |
| P1 | Natural-language resource matching | Returns structured criteria, then applies deterministic hard filters. |
| P1 | Natural-language policy draft | Produces schema-validated proposal, never enforces before human confirmation. |
| P1 | AI incident summary | Shows source-linked summary and explicit human-review status. |
| P1 | Notifications/reminders | In-app notices for decisions and overdue states; no external integration required. |
| P2 | Cross-institution federation, payments, calendar sync, QR device integration | Do not attempt unless all P0 tests pass and time remains. |

# 6. Recommended technical architecture

Use a modular monolith, not microservices. It is easier to finish, test and explain in 48 hours.

| **Layer** | **Recommendation** | **Reason / guardrail** |
| --- | --- | --- |
| Frontend | React + TypeScript + Vite | Fast iteration; typed API contracts; accessible responsive UI. |
| UI | Tailwind CSS or existing chosen component system | Choose one, avoid mixing design systems. UI must expose real backend states. |
| Backend | Python + FastAPI + Pydantic | Clear schemas, API docs, validation and quick testability. |
| Persistence | SQLAlchemy + SQLite for local demo; PostgreSQL if deployment is already reliable | Do not add migration/deployment complexity late. SQLite must use transactions/constraints for conflict handling. |
| Testing | pytest + API integration tests; frontend smoke tests | Prove business rules, not only page rendering. |
| AI adapter | Provider-neutral service interface with one selected model/provider | Keep provider keys server-side; add timeouts, schema validation and deterministic fallback. |
| File evidence | Local/object storage adapter with file type/size limits | Do not expose private evidence publicly. If upload is risky, implement controlled metadata plus small safe image upload. |
| Deployment | One known, judge-accessible host and persistent database | Verify cold start, data persistence, account access and service limits before submission. |

## Backend modules

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

## Frontend modules

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

## Security minimums

Enforce authorization in the backend on every protected endpoint; frontend hiding is not security.

Use server-derived identity/role, not user-supplied role fields in request bodies.

Validate ownership and organization scope for every resource, booking, incident and evidence file.

Use parameterized ORM/database operations; validate inputs and constrain file size/type.

Keep model API keys and secrets in server-side environment variables.

Apply timeouts and safe fallbacks to AI calls; never let AI outage break deterministic booking.

Avoid storing real student IDs, sensitive training documents or personal data for the demo.

Log decisions without logging secrets or unnecessary personal content.

Use a transaction/unique constraint or safe locking strategy to prevent double booking.

Provide a demo reset method that resets only seeded demo data and is unavailable to ordinary users.

# 7. Data model and state machines

## Core entities

| **Entity** | **Minimum fields / purpose** |
| --- | --- |
| User | id, display_name, role, organization_id, demo flag, active status |
| Resource | id, owner_id, name, category, capability tags, location, status, max duration, supervision flag |
| ResourcePolicy | id, resource_id, version, structured requirements, allowed uses, priority policy, effective time, approved_by |
| TrainingRecord | id, user_id, requirement_code, status, verified_by, valid_from/to; demo records clearly synthetic |
| ResourceRequest | id, requester_id, resource_id, purpose, requested interval, status, created_at |
| AllocationDecision | id, request_id, policy_version, outcome, explanation_code, explanation, inputs_snapshot, reviewer_override |
| Booking | id, request_id, start/end, status, approved_by, version |
| AccessContract | id, booking_id, policy_version, requirements snapshot, approved conditions, expiry |
| HandoverReport | id, booking_id, stage IN/OUT, checklist_version, condition, notes, evidence references, actor, timestamp |
| Incident | id, booking_id, reporter_id, category, description, status, responses, resolution, reviewer_id |
| AuditEvent | id, actor_id, entity_type/id, action, timestamp, request_id/correlation_id, before/after summary, previous_hash/hash optional |
| Notification | id, recipient_id, type, related_entity, read_at, created_at |

## Request lifecycle

DRAFT → SUBMITTED → (INELIGIBLE | PENDING_REVIEW | WAITLISTED)

PENDING_REVIEW → APPROVED | REJECTED | WAITLISTED

WAITLISTED → PENDING_REVIEW | CANCELLED | EXPIRED

APPROVED → CANCELLED (subject to policy) | CHECKED_IN

CHECKED_IN → RETURN_PENDING

RETURN_PENDING → CLOSED | INCIDENT_REVIEW

INCIDENT_REVIEW → CLOSED (only after authorized resolution)

Use separate booking and incident states if that makes invariants clearer. Do not overload one status field with unrelated concepts. Define legal transitions centrally and test invalid transitions.

## Critical invariants

No confirmed overlapping booking for the same exclusive resource.

A resource on maintenance hold cannot be approved.

Eligibility is checked on the server at submission and again before approval/check-in where relevant.

Approved contract stores a snapshot of the policy and requirements version.

Only authorized staff can approve/reject or resolve incidents.

Requester cannot approve their own request unless an explicit institutional policy permits a reviewed exception; default is deny.

Check-in/out must reference the correct active booking and cannot be duplicated.

Audit events are generated server-side for critical transitions.

A return condition discrepancy creates a reviewable incident; it does not automatically prove fault.

AI output is treated as untrusted input and validated against a strict schema.

# 8. AI strategy: narrow, testable, reviewable

| **AI capability** | **Input** | **Output** | **Validation / fallback** |
| --- | --- | --- | --- |
| Resource matching (P1) | User's project goal and constraints | Structured need + ranked candidate explanations | Schema validation, deterministic filters; keyword/category search fallback. |
| Policy drafting (P1) | Owner's natural-language policy | Proposed JSON policy + ambiguities/questions | Pydantic/schema validation; human confirms; reject unsafe/unknown rules. |
| Incident summary (P1) | Incident description and selected evidence metadata | Neutral factual summary + missing info checklist | No guilt/liability conclusion; human review; show source data and fallback to original report. |

Do not build a multi-agent runtime into the user-facing product in the 48-hour window. Use separate AI coding roles during development, with a shared contract and independent tests. This is more reliable than making a swarm of agents coordinate live product actions.

## AI safety rules

No model can grant access, waive training, clear maintenance, approve a booking, assign blame or impose a penalty.

The AI provider receives only the minimum data needed; no secrets or unnecessary personal information.

Model output must be parsed and validated; invalid output triggers fallback, not a guessed action.

Every generated policy remains a draft until authorised human approval.

AI recommendation explanations must distinguish facts from suggestions.

Use deterministic sample outputs for judge reliability only if clearly labelled as fallback/demo behaviour; never pretend a model call occurred when it did not.

# 9. API contract outline

GET    /api/resources?query=&category=&available_from=&available_to=

POST   /api/resources

GET    /api/resources/{id}

PATCH  /api/resources/{id}

POST   /api/resources/{id}/policy-drafts

POST   /api/resources/{id}/policies/{version}/activate

POST   /api/requests

GET    /api/requests/mine

GET    /api/manager/requests

POST   /api/requests/{id}/decision

POST   /api/bookings/{id}/check-in

POST   /api/bookings/{id}/check-out

POST   /api/bookings/{id}/extension-requests

POST   /api/bookings/{id}/incidents

GET    /api/incidents/{id}

POST   /api/incidents/{id}/responses

POST   /api/incidents/{id}/resolve

GET    /api/resources/{id}/timeline

GET    /api/resources/{id}/memory

GET    /api/audit?entity_type=&entity_id=

POST   /api/ai/match

POST   /api/ai/summarize-incident

Exact request/response schemas must be agreed before frontend/backend work proceeds in parallel. Every endpoint must return consistent error codes and structured messages, especially for eligibility, conflict and permission failures.

# 10. End-to-end judge scenario

Use one fictional lab, 6–8 resources, 4–6 synthetic users and a controlled scenario. Keep a “Reset demo data” control restricted to the admin/demo environment.

Judge signs in as requester using visible demo credentials.

Judge describes a project need; AI matching returns a suitable resource and explains its fit, or deterministic fallback returns equivalent useful results.

Judge opens the resource and sees requirements, availability, current readiness and exact blockers.

Judge attempts a request without required training; backend blocks it and explains the missing requirement.

Judge switches to an eligible requester or has the fictional manager verify training; submits a request.

A pre-seeded competing request creates a genuine allocation decision; the system shows a published policy and reason.

Manager approves; a versioned Access Contract is created and visible.

Requester checks in, completes the condition checklist and records evidence.

Requester returns the resource, records final condition and closes the session.

For a separate pre-seeded scenario, a condition discrepancy creates an incident for human review.

Judge opens the resource timeline and Resource Memory; counts tie back to visible events and demo data is labelled.

Do not try to force every branch into one transaction. Use two short scenarios if needed: one clean completed lifecycle and one incident/fairness exception.

# 11. Team roles and integration rules

| **Role** | **Owns** | **Must deliver** |
| --- | --- | --- |
| Product / judge journey lead | Build Contract, scope, UX flow, demo data, final narrative and submission checklist | Acceptance criteria, workflow map, final PDF content, each member's truthful contribution statement. |
| Backend engineer | Domain models, APIs, state transitions, policy/eligibility/allocation, audit, persistence | Working API, schema docs, tests, seed/reset script, env example. |
| Frontend engineer | Responsive UI, role-specific routes, forms, loading/error states, API integration | Working user and manager journeys; no fake local-only decisions. |
| AI / integration engineer (if team size allows) | Provider adapter, structured outputs, validation, deterministic fallbacks, AI disclosure | One reliable AI feature, tests for malformed/timeouts, no exposed keys. |
| Independent QA / security reviewer | Acceptance tests, abuse cases, deploy verification and judge simulation | Test evidence, blocking bug list, regression pass. |

If the team has fewer people, combine roles but keep ownership explicit. Avoid two agents editing the same files simultaneously. One integration lead owns the main branch and merges only after tests.

## Parallel-agent protocol

Product lead freezes API/data/state contracts before parallel implementation.

Backend and frontend agents work in separate branches or clearly separated directories.

Every task starts with acceptance criteria and named files; agents must inspect the repository before editing.

Frontend uses generated/mock API fixtures only temporarily and marks them; it must be switched to real API before Ship Gate.

One integration owner runs end-to-end tests on the merged build.

QA agent does not rewrite features while testing; it reports reproducible defects with steps, expected/actual results and severity.

Only the release owner may mark a feature complete after evidence is attached.

# 12. 48-hour execution plan

| **Elapsed time** | **Primary objective** | **Exit gate** |
| --- | --- | --- |
| 0–2h | Read exact official PDF/rubric, confirm scope, choose stack, repo, data model, API/state contracts, judge scenario. | Build Contract and contracts frozen; no coding against unresolved interfaces. |
| 2–8h | Backend skeleton, database, resource/request models, auth/demo roles, frontend shell and resource discovery. | App boots; resource data persists; API contract is live. |
| 8–16h | Eligibility, booking decisions, conflict prevention, policy version, Access Contract and manager queue. | Happy path + ineligible + overlap tests pass. |
| 16–24h | Check-in/out, condition evidence, audit timeline, incident workflow. | Complete lifecycle works from UI through API/database. |
| 24–30h | Resource Memory, readiness blockers, capacity recommendations. | Metrics tie to seeded/persisted records and disclose demo data. |
| 30–35h | One AI feature (matching preferred), schema validation and fallback; other AI only if core is stable. | AI failure does not break core booking. |
| 35–40h | Adversarial tests, accessibility/usability polish, deployment and persistence checks. | No P0 defects; judge can finish without team guidance. |
| 40–44h | Independent judge run, security pass, README, architecture diagram, test notes and AI disclosure. | Evidence-backed Ship Gate passes. |
| 44–46h | Freeze features; repair only P0/P1 defects; redeploy and rerun regression. | Final deployed build matches tested commit. |
| 46–48h | Submission PDF, repo/link permissions, each participant's own form, credentials, verify every link. | Submission checklist complete before deadline. |

If any P0 workflow is broken at hour 30, stop adding AI and analytics. If deployment is unstable at hour 35, simplify architecture rather than starting another integration.

# 13. Backend master prompt

## 13A. Backend implementation master prompt

Copy this prompt into the assigned AI coding agent after the team agrees on the Build Contract.

You are the Backend Lead implementing OpenVault for a 48-hour hackathon. Build only the backend tasks assigned in the approved Build Contract. Do not create a generic booking CRUD app.

STACK (unless repository already establishes another approved stack):
Python, FastAPI, Pydantic, SQLAlchemy, pytest. SQLite for the first reliable demo; use PostgreSQL only if deployment support is already confirmed.

BEFORE CODING:
1. Inspect the repository, existing files, environment and current git status.
2. Read the approved Build Contract, domain model, API contract and state machine.
3. Report conflicts/unknowns before changing interfaces.
4. List the files you will change and acceptance tests for this task.
5. Do not overwrite another agent's work or modify unrelated files.

REQUIRED DOMAIN BEHAVIOUR:
- Resources have owner, location, capability, operational status, policy version, availability and access requirements.
- Eligibility and readiness are server-side domain services.
- AI may propose structured policy, but only an authorized human can activate a validated policy version.
- Booking decisions and allocation explanations are persisted.
- Approved booking creates a snapshot Access Contract.
- Check-in/out requires a valid booking and follows legal state transitions.
- Condition discrepancy creates a reviewable incident; never infer guilt or apply a penalty.
- Critical transitions generate server-side audit events.
- Resource Memory aggregates actual records and identifies demo/seed data.
- No overlapping confirmed reservations for an exclusive resource.

SECURITY:
- Derive actor identity/role from authenticated session or safe demo auth; never trust role fields supplied by client.
- Enforce object-level authorization on every endpoint.
- Validate organization/resource scope.
- Validate every state transition and policy version.
- Keep provider keys in environment variables.
- Bound upload type/size if uploads exist.
- AI calls must have timeouts, strict schema validation and safe fallback.
- Avoid sensitive real user data.

RELIABILITY:
- Use transactions/constraints/locking appropriate to the selected database for conflict prevention.
- Return structured error responses for ineligible, conflicting, unauthorized and invalid-state requests.
- Make repeated submissions idempotent where needed; prevent duplicate check-in/out and duplicate decisions.
- Avoid silently rewriting audit history.
- Do not claim a hash chain proves authenticity; if implemented, describe it as tamper-evident only.

TESTS REQUIRED:
1. Resource create/read/update and persistence.
2. Missing training blocks request and approval.
3. Maintenance hold blocks booking.
4. Two overlapping confirmed bookings cannot both succeed, including concurrent requests if feasible.
5. Unauthorized user cannot approve or resolve incident.
6. Self-approval is denied by default.
7. Policy edits do not silently alter an existing Access Contract.
8. Invalid state transitions are rejected.
9. Duplicate check-in/out is rejected.
10. Condition discrepancy creates incident but no automatic blame.
11. Audit events are created for critical actions.
12. AI malformed response/timeout falls back without breaking core flows.
13. Resource Memory counts reconcile with underlying records.

DELIVERABLES:
- Implemented API and domain services.
- Pydantic request/response schemas.
- Database models and initialization/migration approach.
- Seed script with fictional data and restricted demo reset.
- pytest tests and exact commands to run them.
- OpenAPI docs.
- .env.example with placeholder names only.
- A concise report: IMPLEMENTED / VERIFIED / NOT VERIFIED / RISKS / FILES CHANGED.

Do not build fake endpoints or return hard-coded success for operations that should persist. If a requirement cannot fit, report it honestly and propose the smallest safe scope reduction.

# 14. Frontend master prompt

## 14A. Frontend implementation master prompt

Copy this prompt into the assigned AI coding agent after the team agrees on the Build Contract.

You are the Frontend Lead for OpenVault. Build a polished, accessible, responsive product interface connected to the real backend. This is not a static dashboard prototype.

STACK (unless repository says otherwise):
React + TypeScript + Vite. Use the existing approved UI system; do not add multiple component libraries.

BEFORE CODING:
1. Inspect the repository and current routes/components.
2. Read the approved Build Contract, role matrix, API schemas and state machines.
3. Confirm API base URL and error shapes with the backend lead.
4. List files to change and acceptance criteria.
5. Do not edit backend files or duplicate business rules in the UI.

CORE ROUTES / SCREENS:
- Demo sign-in / role selector with clearly labelled fictional demo accounts.
- Resource discovery with search, category/status/availability filters.
- Resource detail: capability, location, policy requirements, readiness, exact blockers, availability and history summary.
- Request flow: purpose, requested interval, eligibility result, conflict alternatives and submit state.
- Requester dashboard: pending/approved/rejected/waitlisted requests and explanations.
- Manager queue: request context, eligibility evidence, competing demand, allocation explanation, approve/reject/waitlist with required reason.
- Access Contract view: approved conditions, policy version, period, supervision, permitted use and status.
- Check-in/out: checklist, condition choice, optional safe evidence upload, confirmation and timestamps.
- Incident flow: neutral report, responses, review status and resolution reason.
- Resource Memory: utilisation/idle/blocked hours, waitlist demand and recommendations, with date range and DEMO DATA label.
- Audit timeline: actor, event, timestamp, action and reason where applicable.

UX RULES:
- First screen must explain the product in one sentence and show the main action.
- No dead buttons, fake metrics, hard-coded success messages or non-functional AI cards.
- Every async operation needs loading, success, empty and error states.
- Display backend eligibility/conflict reasons verbatim or map known error codes to clear user language.
- Do not infer permission from hidden buttons; the backend is authoritative.
- Explain blocked states and the next allowed action.
- Use accessible labels, keyboard focus, sufficient contrast and responsive layouts.
- Distinguish AI suggestions from verified facts and human decisions.
- Mark all synthetic institutions/users/metrics as demo data.
- Keep the main workflow obvious; do not bury it beneath analytics.

API INTEGRATION:
- Use typed API client and shared TypeScript types generated from or aligned with backend schemas.
- No local-only mutation for approvals, bookings, check-in/out, incidents or audit history.
- After mutation, refresh or update from authoritative API response.
- Handle 401/403/409/422/500 and network timeout explicitly.
- Prevent double-click duplicate submissions.
- Never store secret API keys in frontend code.

ACCEPTANCE:
1. A judge can complete the core journey without developer explanation.
2. An ineligible request displays a clear backend-derived reason.
3. A competing request displays the actual allocation outcome and explanation.
4. Approval creates a visible Access Contract.
5. Check-in and return records persist after refresh.
6. Incident creation and manager resolution work through API.
7. Resource Memory reflects persisted records and shows demo disclaimer.
8. All visible controls work or are clearly disabled with a reason.
9. No critical errors in browser console.
10. Responsive layout works on a common laptop viewport and mobile width.

DELIVERABLES:
- Implemented routes/components.
- Typed API integration.
- Minimal automated/UI smoke tests where time permits.
- README section describing routes and demo accounts.
- Report IMPLEMENTED / VERIFIED / NOT VERIFIED / RISKS / FILES CHANGED.

# 15. AI agent orchestration prompts

## 15A. Multi-agent engineering orchestrator

Copy this prompt into the assigned AI coding agent after the team agrees on the Build Contract.

You are the Engineering Orchestrator for OpenVault. Coordinate Product, Backend, Frontend, AI, QA/Security and Release agents. The goal is a reliable judge-completable product, not maximum code volume.

SOURCE OF TRUTH:
- Approved Build Contract
- Domain model and state machines
- OpenAPI/API schemas
- Acceptance criteria
- Shared task board

RULES:
1. Never ask two agents to edit the same files concurrently.
2. Freeze contracts before parallel backend/frontend implementation.
3. Give each agent a small task with exact scope, file ownership, dependencies and acceptance tests.
4. Require repository inspection before any edits.
5. Agents report IMPLEMENTED, VERIFIED, NOT VERIFIED, RISKS and FILES CHANGED.
6. Treat AI-generated code as untrusted until tests pass.
7. Do not merge a feature because an agent says it is complete.
8. Keep the user-facing AI surface to resource matching, policy drafting and/or incident summarisation only if P0 is stable.
9. If a P0 feature is broken, stop P2 work and redirect capacity to repair.
10. Maintain an explicit known-defects list and time budget.
11. One integrator owns merges and final deployed commit.
12. Preserve honest attribution and disclose significant AI tools.

AGENT WORKSTREAMS:
A. Product/UX: journey, requirements, demo story, accessibility.
B. Backend: domain rules, persistence, APIs, tests.
C. Frontend: routes, forms, API integration, errors and responsive UI.
D. AI adapter: structured outputs, schema validation, timeout/fallback.
E. QA/Security: independent tests and abuse attempts; do not silently change production code.
F. Release/docs: deployment, README, architecture, credentials, disclosures and submission checklist.

INTEGRATION GATES:
G1: App boots locally and DB persists.
G2: Eligibility, authorization and conflict tests pass.
G3: Full lifecycle works via UI/API.
G4: Incidents and audit work.
G5: AI failure does not break core.
G6: Deployed version passes the same critical smoke tests.
G7: Submission artifacts and every team member's individual form are complete.

Do not promise a score or winning. Report risks early, ask for a decision only when a true product ambiguity blocks progress, and otherwise choose the simplest reversible implementation consistent with the contract.

## 15B. AI integration agent

Copy this prompt into the assigned AI coding agent after the team agrees on the Build Contract.

You are the AI Integration Engineer for OpenVault. Add only a bounded, testable AI capability after core booking is stable.

Preferred first feature: natural-language project-to-resource matching.
Input: project goal, material/capability needs, time range, location and constraints.
Output: validated JSON containing extracted requirements, ranked resource IDs from supplied candidates, concise reasons and uncertainties.
Never invent resources or availability. The backend supplies candidate resources; deterministic filters enforce hard requirements after model output.

Optional second feature: policy draft compiler.
Input: owner-authored natural-language draft and allowed policy schema.
Output: proposed structured policy plus ambiguity questions.
Never activate the policy. A manager must review and explicitly confirm it. Unknown, contradictory or unsafe requirements must be flagged, not guessed.

Optional third feature: neutral incident summary.
Summarise only supplied report facts and list missing information. Do not infer guilt, liability, damage cause or penalty.

IMPLEMENTATION:
- Provider abstraction and server-side key handling.
- Strict Pydantic/JSON schema validation.
- Timeout, retry only where safe, token/cost limits and structured errors.
- No sensitive user data in prompts.
- Deterministic fallback that is disclosed as fallback.
- Unit tests for valid, malformed, hallucinated-ID, timeout and refusal outputs.
- Log metadata needed for debugging, not secrets or unnecessary personal content.

If AI integration threatens the core lifecycle or deadline, ship deterministic matching first and document AI as not implemented. Never fake an AI call.

## 15C. Independent QA/security agent

Copy this prompt into the assigned AI coding agent after the team agrees on the Build Contract.

You are the independent QA and security reviewer for OpenVault. Do not assume features work because the implementation agent says so. Test the deployed candidate and API.

Run the primary journey:
resource discovery → requirements → blocked eligibility attempt → eligible request → competing request/allocation → manager approval → Access Contract → check-in → return → audit → Resource Memory.

Adversarial cases:
- requester attempts manager endpoint
- user accesses another user's booking/evidence
- self-approval
- expired/missing training
- maintenance hold
- overlapping booking requests submitted nearly simultaneously
- request cancelled after approval
- duplicate check-in/out
- check-in outside booking window
- extension after another booking exists
- policy changes after approval
- audit event omitted or altered
- evidence URL publicly exposed
- incident resolved by unauthorized role
- malformed AI JSON, fake resource ID, timeout, prompt injection in incident text
- Resource Memory metrics do not reconcile with records
- refresh/restart causes data loss

For every defect record:
ID, severity (P0/P1/P2), environment/commit, exact reproduction steps, expected result, actual result, evidence, likely owner.

P0 means core journey/security/data integrity broken. P1 means significant requirement broken with workaround. P2 means polish or non-core defect.

Do not fix defects silently unless assigned; return a reproducible report. Re-test fixes and related regressions. Never claim tests ran if they did not.

## 15D. Ruthless judge agent

Copy this prompt into the assigned AI coding agent after the team agrees on the Build Contract.

Act as a strict CodeVerse judge with no developer assistance. Use the supplied official rubric and also cross-check the problem-statement rubric if both are provided. Do not assume one supersedes the other until the organiser's official instructions confirm it.

Use only the deployed link and README credentials. Attempt the core journey without being guided. Score evidence, not promises.

Ask:
1. Is the problem and target user clear in 15 seconds?
2. Does this go beyond generic booking?
3. Can I discover a resource and understand exact blockers?
4. Are safety and eligibility rules enforced by the backend?
5. Can I create competing demand and understand the allocation?
6. Is the approved contract a versioned snapshot?
7. Can I complete handover/return and inspect audit events?
8. Are incidents reviewable by a human?
9. Do capacity insights reconcile with records and identify demo data?
10. Does AI have a necessary, bounded job and safe fallback?
11. Can a normal user bypass role or state restrictions?
12. Does the deployed build match the repository and README?

Return:
- score per criterion with evidence
- hard deductions
- P0 blockers
- originality weaknesses
- confusing UI elements
- unsupported claims
- five judge questions the team must answer
- final ship/no-ship recommendation

Do not reward effort, complexity, AI-agent count or visual polish if the workflow is broken. Do not inflate the score. Do not invent evidence.

## 15E. Release and submission agent

Copy this prompt into the assigned AI coding agent after the team agrees on the Build Contract.

You are the Release Engineer for OpenVault. Do not add features. Prepare the tested candidate for evaluation.

Verify:
- production build succeeds
- deployed link opens in a fresh/private browser session
- judge credentials work and are clearly documented
- seeded demo data is fictional and visibly labelled
- persistent database survives refresh/redeploy as expected
- core lifecycle works on deployed environment
- all external API keys are server-side
- README has setup, env variables, seed/reset, tests, architecture, routes, roles and limitations
- repository is accessible to judges
- no secrets, personal data or unlicensed assets are committed
- significant AI tools/models/APIs and pre-existing components are disclosed
- each participant has submitted their own form if required
- project PDF and all required links are complete before deadline
- final deployed version corresponds to a known commit/tag

Return a checklist with PASS / FAIL / NOT VERIFIED and evidence. Never mark an item PASS without checking it. If deployment is unstable, report it and recommend the simplest reliable fix.

# 16. Ruthless ship gate and scorecard

| **Gate** | **Must pass before submission** |
| --- | --- |
| Product | Judge can explain the problem and value after a short first look. |
| Core journey | One clean booking-to-return flow works through UI, API and database. |
| Eligibility | Ineligible request is blocked server-side with an understandable reason. |
| Concurrency | Conflicting reservations cannot both be confirmed. |
| Permissions | Requester cannot approve, edit another user's record or resolve incidents. |
| Access Contract | Approved policy snapshot remains inspectable after policy edits. |
| Handover | Check-in/out records persist and duplicate/invalid transitions fail. |
| Incidents | Human review exists; no automated guilt, penalty or liability decision. |
| Audit | Critical decisions and transitions have actor/time/action records. |
| Capacity insight | Every displayed metric/recommendation traces to records and has a date range. |
| AI | Structured output validated; timeout/malformed output has safe fallback; core remains usable. |
| Usability | Loading, empty, error, success and disabled states are clear; no dead controls. |
| Deployment | Fresh browser can access the product and use credentials; data persists. |
| Documentation | README, architecture, tests, limitations, AI disclosure and team roles complete. |
| Integrity | No prebuilt project presented as built during event; contributions/disclosures truthful. |

## Score target: treat as a target, never a promise

Aim for full credit in working product and reliability by proving the journey, not by adding features. The supplied challenge rubric and CodeVerse page currently publish different scoring splits. Use the organiser-provided official submission PDF/form as final authority; design to satisfy both sets of criteria.

Ship decision: any P0 defect in access control, double booking, persistence, return lifecycle or deployment means NO SHIP until fixed or the affected feature is honestly removed from scope.

# 17. Demo data and script

| **Demo item** | **Suggested seed** |
| --- | --- |
| Institution | Fictional “Northstar Engineering Lab” — explicitly marked DEMO. |
| Resources | 3D printer, camera kit, oscilloscope training station, electronics bench, meeting/project room, one resource on maintenance hold. |
| Users | Requester A (eligible), Requester B (low recent usage), Requester C (missing training), Lab Manager, Admin/Auditor. |
| Bookings | One completed booking, one pending request, one competing request, one waitlisted request, one upcoming booking. |
| Incident | One synthetic condition discrepancy marked under human review, no attribution of blame. |
| Metrics | Seeded usage and demand events with visible “DEMO DATA — not live institutional statistics” label. |

Make the judge journey resilient: include one clean scenario and one exception scenario. Provide credentials on the landing/README and avoid any dependency on external email delivery or real institutional login.

# 18. Submission and team checklist

Confirm the exact official problem statement, deadline, official PDF template and applicable judging rubric.

Confirm team size and list every member accurately.

Every participant files their own submission if the event requires individual submissions; do not assume one teammate's form covers the rest.

Public/judge-accessible application link works in a fresh session.

Repository access is set correctly; commit history reflects honest build-window work.

README contains setup, deployment, demo accounts, test commands, data reset and architecture.

Project PDF covers problem, target users, workflow, implemented features, stack, architecture, AI/tools/APIs, security/privacy/fairness, limitations and future work.

State completed, partial and unimplemented features honestly.

Disclose AI coding tools, model/API use, external libraries, templates and pre-existing components as required.

Remove secrets, real personal information, institution-confidential data and unlicensed assets.

Test the deployed version after the final deploy; don't rely only on localhost.

Keep a screenshot/log of successful test runs and known limitations; never fabricate test evidence.

Check every URL, credential, file and form before deadline.

# 19. Final recommendation

Build OpenVault only if the team commits to the complete access lifecycle and the readiness-to-capacity-recovery loop. Do not market it as unprecedented. Its defensible differentiation is the integration and the quality of the implementation.

The strongest 48-hour submission is not the largest architecture. It is a small, coherent system that explains why access is blocked, enforces the actual rules, allocates scarce capacity transparently, records the handover, preserves human review and derives honest capacity insights from its own events.

If the core flow is not stable by the halfway point, cut AI policy drafting and incident summarisation first. Preserve the real backend workflow, conflict handling, audit, one useful capacity insight and an independently usable judge experience.

# 20. Research references

**Official CodeVerse India event page — dates, format, judging criteria, deliverables and rules — **https://wecodecoders.in/events/codeverse-india

**I-STEM / Office of the Principal Scientific Adviser — purpose and national resource-sharing footprint — **https://www.psa.gov.in/i-stem

**I-STEM guidelines — institutional and user SOPs — **https://www.istem.gov.in/guidelines

**I-STEM registration — institutional resource listing and access context — **https://www.istem.gov.in/registration

**CASRAI equipment booking software guide — baseline features in lab booking products — **https://casrai.org/guides/equipment-booking-software

**CASRAI core-facility equipment sharing agreements — usage tracking and priority-access baseline — **https://casrai.org/guides/core-facility-equipment-sharing-agreements

**University of Melbourne research facilities — iLab booking context — **https://research.unimelb.edu.au/facilities/infrastructure/ilab/ilab-booking-system

**Inkloom AI: How it works — staged, reviewable generation approach; relevant as a design analogy, not a statement of CodeVerse scoring internals — **https://inkloom.ai/how-it-works

Research note: official pages and available search results were reviewed on 30 October 2026. This document does not claim access to private judging sheets, non-public winner submissions or organiser internal scoring notes.

OPENVAULT • CODEVERSE TEAM BUILD PACK • PLANNING DOCUMENT