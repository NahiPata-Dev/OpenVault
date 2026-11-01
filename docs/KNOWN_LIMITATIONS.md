# Known Limitations

OpenVault is an evaluation prototype, not an institutional system of record.

## Data and integrations

- Seeded organizations, people, resources, requests, bookings, training,
  incidents, audit records, and dashboard metrics are fictional sample data.
  City and area names may be real, but they do not imply that a real institution
  or facility participates.
- The application is not integrated with institutional identity, student
  records, training systems, calendars, facilities, or resource-management
  systems.
- Payments, deposits, fines, binary evidence uploads, and booking extensions
  are not supported.
- Access policies and operating schedules are application data. A displayed
  availability or eligibility result does not guarantee a booking; the server
  rechecks the submitted request and an authorized manager makes the decision.

## Judge access

- One-click judge entry is an evaluation shortcut controlled by
  `JUDGE_LOGIN_ENABLED` and is disabled by default.
- When enabled, each judge role maps to one fixed fictional seeded account.
  Judge access cannot sign in as a registered user or an institution
  administrator. It does not provide a second requester identity for testing
  competition between two requesters.
- The requester and lab-manager judge roles can perform the normal actions
  permitted to their sample roles. Judge mode blocks admin-destructive actions
  such as demo reset, but it does not make all judge roles read-only; the
  auditor role is read-only.
- Disable judge access in real deployments. Do not use it as an identity or
  access-control mechanism for a production service.

## Assistant and decisions

- Rules-based resource matching is available without an AI provider. AI
  interpretation and phrasing depend on optional provider configuration.
- The assistant can prepare a request draft but cannot submit, approve, or
  waitlist a request or override eligibility.
- Eligibility checks do not replace a manager's review or the service's
  final conflict and policy checks.
