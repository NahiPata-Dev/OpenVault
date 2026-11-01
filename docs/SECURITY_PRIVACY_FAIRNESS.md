# Security, Privacy, and Fairness

## Sample-data boundary

OpenVault's seeded institutions and people are fictional. Some city and area
names are real locations; they do not identify participating institutions.
Seeded booking, training, incident, audit, and metric records are illustrative
and must not be presented as live institutional statistics.

Do not enter real student, staff, health, identity, or other sensitive
information into this evaluation prototype. The application is not connected
to institutional identity or records systems. Configure and protect the
deployment database and signing secret as production credentials; never commit
secrets to source control.

## Judge access boundary

- `JUDGE_LOGIN_ENABLED` defaults to `false`. Enable it only for an evaluation
  deployment that needs the Judge access panel.
- Each one-click role signs in one fixed seeded account marked as demo data.
  The request accepts a role, not an account identifier or password, and does
  not select registered users or an administrator.
- Judge login uses the signed HttpOnly session cookie and marks the session as
  judge mode. The server applies role authorization; judge sessions cannot
  access institution-admin destructive operations such as demo reset.
- The judge API is rate-limited to 30 calls per 10 minutes per IP. Successful
  judge login and role switching are recorded as audit events.
- Normal email/password login and registration remain separate flows. Judge
  login does not reveal a shared credential.
- This feature is an evaluation shortcut, not a production authentication
  method. Keep it disabled in real deployments and use the deployment's
  approved identity provider and access controls.

The auditor judge role is read-only. Requester and lab-manager judge roles can
make the ordinary requests and decisions allowed for those fixed sample
accounts; their actions may change sample records. They cannot use judge mode
to act as a registered user or institution administrator.

## Fairness and human oversight

- Eligibility requirements and blockers are shown to the requester; a manager
  reviews each request and records a reason for a decision.
- Allocation uses the configured, disclosed rules. It does not use priority
  tiers; when the rules do not resolve competing requests, the manager chooses
  and records a reason.
- The assistant may help find resources and prepare a draft. It cannot make
  allocation, approval, or waitlist decisions, and cannot override server-side
  eligibility or conflict checks.
- Incident review records facts and a human rationale. The system does not
  infer blame or apply a penalty automatically.
- AI-provider use is optional. When configured, do not send sensitive or
  confidential information in assistant prompts; the configured provider may
  process prompt content under its own service terms.

## Operational cautions

Audit events and account data are stored in the configured application
database. Operators must apply appropriate access, retention, backup, and
incident-response controls to that environment. This prototype does not claim
regulatory certification or a security audit.
