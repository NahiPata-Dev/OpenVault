import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { DemoAccount } from "../api/types";
import { EmptyState, ErrorState, Loading } from "../components/Feedback";
import { PageHeading, StatusBadge } from "../components/PageHeading";
import { formatIST, istInputToISO, statusLabel } from "../lib/format";

interface Blocker {
  code: string;
  message: string;
}

interface ManagerRequest {
  id: string;
  requester_id: string;
  resource_id: string;
  purpose: string;
  start_at: string;
  end_at: string;
  status: string;
  created_at: string;
}

interface Candidate {
  request_id: string;
  requester_id: string;
  created_at: string;
  completed_bookings_30d: number;
  booked_hours_30d: number;
  newcomer: boolean;
  within_usage_limit: boolean;
}

interface Recommendation {
  recommendation: string;
  inputs_snapshot: {
    algorithm_version: string;
    window_start: string;
    window_end: string;
    usage_limit_hours: number;
    candidates: Candidate[];
    ranked_request_ids: string[];
    excluded_over_limit_request_ids: string[];
    tie_group: string[];
  };
}

interface ManagerQueueItem {
  request: ManagerRequest;
  eligibility: { eligible: boolean; blockers: Blocker[] };
  allocation_recommendation: Recommendation;
}

interface Resource {
  id: string;
  name: string;
}

export function ManagerQueuePage() {
  const [items, setItems] = useState<ManagerQueueItem[]>([]);
  const [users, setUsers] = useState<Map<string, string>>(new Map());
  const [resources, setResources] = useState<Map<string, string>>(new Map());
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [queue, accounts, resourceList] = await Promise.all([
        api.get<{ items: ManagerQueueItem[]; total: number }>("/manager/requests"),
        api.get<{ accounts: DemoAccount[] }>("/auth/demo-accounts"),
        api.get<{ items: Resource[]; total: number }>("/resources"),
      ]);
      setItems(queue.items);
      setUsers(new Map(accounts.accounts.map((account) => [account.id, account.display_name])));
      setResources(new Map(resourceList.items.map((resource) => [resource.id, resource.name])));
    } catch (loadError) {
      setError(loadError);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function decide(event: FormEvent<HTMLFormElement>, requestId: string) {
    event.preventDefault();
    const outcome = (event.nativeEvent as SubmitEvent).submitter;
    if (!(outcome instanceof HTMLButtonElement)) return;
    const reason = reasons[requestId]?.trim() ?? "";
    if (!reason) return;
    setPendingId(requestId);
    setActionError(null);
    try {
      await api.post(`/requests/${requestId}/decision`, {
        outcome: outcome.value,
        reason,
        override_reason: null,
      });
      setReasons((current) => ({ ...current, [requestId]: "" }));
      await load();
    } catch (decisionError) {
      setActionError(decisionError);
    } finally {
      setPendingId(null);
    }
  }

  return (
    <>
      <PageHeading
        title="Manager queue"
        description="Review eligibility and allocation guidance. Recommendations do not make decisions."
      />
      {actionError !== null && <ErrorState error={actionError} />}
      {loading && <Loading label="Loading the manager queue…" />}
      {error !== null && <ErrorState error={error} />}
      {!loading && error === null && items.length === 0 && <EmptyState>No requests are visible in your manager queue.</EmptyState>}
      {!loading && error === null && items.length > 0 && (
        <div className="request-list">
          {items.map(({ request, eligibility, allocation_recommendation: recommendation }) => {
            const snapshot = recommendation.inputs_snapshot;
            const candidate = snapshot.candidates.find((row) => row.request_id === request.id);
            return (
              <article className="request-card" key={request.id}>
                <div className="card-title-row">
                  <div>
                    <p className="eyebrow">{resources.get(request.resource_id) ?? "Resource"}</p>
                    <h2>{statusLabel(request.purpose)}</h2>
                  </div>
                  <StatusBadge value={request.status} />
                </div>
                <dl className="request-details">
                  <div><dt>Requester</dt><dd>{users.get(request.requester_id) ?? request.requester_id}</dd></div>
                  <div><dt>Requested window</dt><dd>{formatIST(request.start_at)} – {formatIST(request.end_at)}</dd></div>
                  <div><dt>Submitted</dt><dd>{formatIST(request.created_at)}</dd></div>
                  <div><dt>Eligibility</dt><dd>{eligibility.eligible ? "Eligible" : "Not eligible"}</dd></div>
                </dl>
                {!eligibility.eligible && (
                  <ul className="blocker-list">
                    {eligibility.blockers.map((blocker, index) => <li className="blocker-item" key={`${blocker.code}-${index}`}><strong>{blocker.code}</strong><p>{blocker.message}</p></li>)}
                  </ul>
                )}
                <section className="recommendation-box">
                  <h3>Allocation recommendation: {statusLabel(recommendation.recommendation)}</h3>
                  <p>Backend recommendation only; the manager makes and records the decision.</p>
                  <p>Usage window: {formatIST(snapshot.window_start)} – {formatIST(snapshot.window_end)} · Limit: {snapshot.usage_limit_hours} booked hours</p>
                  {candidate && (
                    <p>
                      Requester context: {candidate.newcomer ? "Newcomer for this resource" : `${candidate.completed_bookings_30d} completed bookings`}
                      {" · "}{candidate.booked_hours_30d} booked hours in 30 days
                      {" · "}{candidate.within_usage_limit ? "Within usage limit" : "Over usage limit"}
                    </p>
                  )}
                  {snapshot.tie_group.length > 1 && <p>Recommendation tie: manager choice is required for {snapshot.tie_group.length} contenders.</p>}
                </section>
                {request.status === "PENDING_REVIEW" && (
                  <form className="decision-form" onSubmit={(event) => void decide(event, request.id)}>
                    <label className="field-label" htmlFor={`decision-reason-${request.id}`}>Decision reason (required)</label>
                    <textarea
                      id={`decision-reason-${request.id}`}
                      className="textarea"
                      required
                      maxLength={2000}
                      value={reasons[request.id] ?? ""}
                      onChange={(event) => setReasons((current) => ({ ...current, [request.id]: event.target.value }))}
                      disabled={pendingId === request.id}
                    />
                    <div className="card-actions">
                      <button className="button button-primary" type="submit" value="approved" disabled={pendingId === request.id || !reasons[request.id]?.trim()}>{pendingId === request.id ? "Saving…" : "Approve"}</button>
                      <button className="button button-secondary" type="submit" value="rejected" disabled={pendingId === request.id || !reasons[request.id]?.trim()}>Reject</button>
                      <button className="button button-secondary" type="submit" value="waitlisted" disabled={pendingId === request.id || !reasons[request.id]?.trim()}>Waitlist</button>
                    </div>
                  </form>
                )}
              </article>
            );
          })}
        </div>
      )}
    </>
  );
}

interface ResourceDetail {
  resource: { id: string; name: string };
  active_policy: {
    structured_requirements: { training_codes: string[] };
  } | null;
}

export function TrainingPage() {
  const [accounts, setAccounts] = useState<DemoAccount[]>([]);
  const [resources, setResources] = useState<Resource[]>([]);
  const [selectedResource, setSelectedResource] = useState("");
  const [requirements, setRequirements] = useState<string[]>([]);
  const [userId, setUserId] = useState("");
  const [requirementCode, setRequirementCode] = useState("");
  const [status, setStatus] = useState("valid");
  const [validFrom, setValidFrom] = useState("");
  const [validTo, setValidTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [formError, setFormError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void Promise.all([
      api.get<{ accounts: DemoAccount[] }>("/auth/demo-accounts"),
      api.get<{ items: Resource[]; total: number }>("/resources"),
    ]).then(([accountResult, resourceResult]) => {
      if (!active) return;
      setAccounts(accountResult.accounts.filter((account) => account.role === "requester"));
      setResources(resourceResult.items);
    }).catch((loadError: unknown) => active && setError(loadError))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!selectedResource) {
      setRequirements([]);
      return;
    }
    let active = true;
    void api.get<ResourceDetail>(`/resources/${selectedResource}`).then((detail) => {
      if (!active) return;
      const codes = detail.active_policy?.structured_requirements.training_codes ?? [];
      setRequirements(codes);
      setRequirementCode(codes[0] ?? "");
    }).catch((loadError: unknown) => active && setFormError(loadError));
    return () => { active = false; };
  }, [selectedResource]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setFormError(null);
    setSaved(null);
    try {
      const result = await api.post<{ training_record: { id: string } }>("/training-records", {
        user_id: userId,
        requirement_code: requirementCode.trim(),
        status,
        valid_from: istInputToISO(validFrom),
        valid_to: validTo ? istInputToISO(validTo) : null,
      });
      setSaved(`Training record ${result.training_record.id} was recorded by the backend.`);
    } catch (submitError) {
      setFormError(submitError);
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <PageHeading title="Training sign-off" description="Record a training status for a demo user and a resource requirement." />
      {loading && <Loading label="Loading users and resources…" />}
      {error !== null && <ErrorState error={error} />}
      {!loading && error === null && (
        accounts.length === 0 || resources.length === 0 ? (
          <EmptyState>No users or resources are available for a training sign-off.</EmptyState>
        ) : <section className="panel form-panel">
          <form onSubmit={(event) => void submit(event)}>
            <label className="field-label" htmlFor="training-user">User</label>
            <select id="training-user" className="select" required value={userId} onChange={(event) => setUserId(event.target.value)} disabled={pending}>
              <option value="">Select a requester</option>
              {accounts.map((account) => <option value={account.id} key={account.id}>{account.display_name}</option>)}
            </select>

            <label className="field-label" htmlFor="training-resource">Resource</label>
            <select id="training-resource" className="select" required value={selectedResource} onChange={(event) => setSelectedResource(event.target.value)} disabled={pending}>
              <option value="">Select a resource</option>
              {resources.map((resource) => <option value={resource.id} key={resource.id}>{resource.name}</option>)}
            </select>
            <p className="helper">The backend stores the training record by requirement code; resource requirements are shown for reference.</p>

            <label className="field-label" htmlFor="training-code">Requirement code</label>
            {requirements.length > 0 ? (
              <select id="training-code" className="select" required value={requirementCode} onChange={(event) => setRequirementCode(event.target.value)} disabled={pending}>
                {requirements.map((code) => <option value={code} key={code}>{code}</option>)}
              </select>
            ) : (
              <input id="training-code" className="input" required maxLength={100} value={requirementCode} onChange={(event) => setRequirementCode(event.target.value)} disabled={pending} />
            )}

            <div className="form-grid training-grid">
              <div>
                <label className="field-label" htmlFor="training-status">Training status</label>
                <select id="training-status" className="select" value={status} onChange={(event) => setStatus(event.target.value)} disabled={pending}>
                  <option value="valid">Valid</option>
                  <option value="expired">Expired</option>
                  <option value="revoked">Revoked</option>
                </select>
              </div>
              <div>
                <label className="field-label" htmlFor="valid-from">Valid from (IST)</label>
                <input id="valid-from" className="input" type="datetime-local" required value={validFrom} onChange={(event) => setValidFrom(event.target.value)} disabled={pending} />
              </div>
              <div>
                <label className="field-label" htmlFor="valid-to">Valid to (IST, optional)</label>
                <input id="valid-to" className="input" type="datetime-local" value={validTo} onChange={(event) => setValidTo(event.target.value)} disabled={pending} />
              </div>
            </div>
            {formError !== null && <ErrorState error={formError} />}
            {saved && <p className="result-panel result-positive" role="status">{saved}</p>}
            <button className="button button-primary mt-4" type="submit" disabled={pending || !userId || !selectedResource || !requirementCode.trim() || !validFrom}>
              {pending ? "Recording…" : "Record training sign-off"}
            </button>
          </form>
        </section>
      )}
    </>
  );
}

interface AuditEvent {
  entity_id: string;
}

interface Incident {
  id: string;
  booking_id: string;
  reporter_id: string;
  category: string;
  description: string;
  status: string;
  responses: { actor_id: string; message: string; created_at: string }[];
  resolution: { outcome: string; rationale: string; resolved_at: string } | null;
  reviewer_id: string | null;
  created_at: string;
  updated_at: string;
}

interface IncidentDetailResponse {
  incident: Incident;
  booking: { id: string; request_id: string; status: string };
}

async function loadIncidents(): Promise<Incident[]> {
  const audit = await api.get<{ items: AuditEvent[] }>("/audit?entity_type=incident");
  const incidentIds = [...new Set(audit.items.map((event) => event.entity_id))];
  return Promise.all(
    incidentIds.map(async (id) => {
      const result = await api.get<IncidentDetailResponse>(`/incidents/${id}`);
      return result.incident;
    }),
  );
}

export function IncidentListPage() {
  const [items, setItems] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    void loadIncidents().then((incidents) => active && setItems(incidents))
      .catch((loadError: unknown) => active && setError(loadError))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  return (
    <>
      <PageHeading title="Incidents" description="Review incidents visible within your manager scope." />
      {loading && <Loading label="Loading incidents…" />}
      {error !== null && <ErrorState error={error} />}
      {!loading && error === null && items.length === 0 && <EmptyState>No incidents are present in the scoped audit history.</EmptyState>}
      {!loading && error === null && items.length > 0 && (
        <div className="request-list">
          {items.map((incident) => (
            <article className="request-card" key={incident.id}>
              <div className="card-title-row">
                <div><p className="eyebrow">{statusLabel(incident.category)}</p><h2>{incident.description}</h2></div>
                <StatusBadge value={incident.status} />
              </div>
              <p className="muted">Incident {incident.id} · Booking {incident.booking_id} · {formatIST(incident.created_at)}</p>
              <Link className="button button-secondary" to={`/manager/incidents/${incident.id}`}>Open incident</Link>
            </article>
          ))}
        </div>
      )}
    </>
  );
}

export function IncidentDetailPage() {
  const { incidentId = "" } = useParams();
  const [data, setData] = useState<IncidentDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [rationale, setRationale] = useState("");
  const [outcome, setOutcome] = useState("resolved");
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.get<IncidentDetailResponse>(`/incidents/${incidentId}`));
    } catch (loadError) {
      setError(loadError);
    } finally {
      setLoading(false);
    }
  }, [incidentId]);

  useEffect(() => { void load(); }, [load]);

  async function resolve(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setActionError(null);
    setSaved(false);
    try {
      await api.post(`/incidents/${incidentId}/resolve`, { outcome, rationale: rationale.trim() });
      setSaved(true);
      await load();
    } catch (resolveError) {
      setActionError(resolveError);
    } finally {
      setPending(false);
    }
  }

  if (loading) return <Loading label="Loading incident details…" />;
  if (error !== null) return <ErrorState error={error} />;
  if (!data) return <EmptyState>Incident details are not available.</EmptyState>;

  const { incident, booking } = data;
  return (
    <>
      <Link className="back-link" to="/manager/incidents">← Back to incidents</Link>
      <PageHeading title="Incident detail" description={`${statusLabel(incident.category)} · ${statusLabel(incident.status)}`} />
      <section className="panel">
        <h2>Incident record</h2>
        <dl className="request-details">
          <div><dt>Description</dt><dd>{incident.description}</dd></div>
          <div><dt>Reported</dt><dd>{formatIST(incident.created_at)}</dd></div>
          <div><dt>Booking</dt><dd>{booking.id} · {statusLabel(booking.status)}</dd></div>
          <div><dt>Requester / reporter ID</dt><dd>{incident.reporter_id}</dd></div>
        </dl>
        <h3>Responses</h3>
        {incident.responses.length === 0 ? (
          <p className="muted">No responses have been recorded.</p>
        ) : (
          <ul className="response-list">
            {incident.responses.map((response, index) => (
              <li key={`${response.actor_id}-${response.created_at}-${index}`}>
                <p>{response.message}</p>
                <p className="helper">{response.actor_id} · {formatIST(response.created_at)}</p>
              </li>
            ))}
          </ul>
        )}
        {incident.resolution && (
          <div className="decision-explanation">
            <p><strong>{statusLabel(incident.resolution.outcome)}</strong> · {formatIST(incident.resolution.resolved_at)}</p>
            <p>{incident.resolution.rationale}</p>
          </div>
        )}
        {!incident.resolution && (
          <form className="decision-form" onSubmit={(event) => void resolve(event)}>
            <h3>Resolve incident</h3>
            <label className="field-label" htmlFor="incident-outcome">Outcome</label>
            <select id="incident-outcome" className="select" value={outcome} onChange={(event) => setOutcome(event.target.value)} disabled={pending}>
              <option value="resolved">Resolved</option>
              <option value="dismissed">Dismissed</option>
            </select>
            <label className="field-label" htmlFor="incident-rationale">Rationale (required)</label>
            <textarea id="incident-rationale" className="textarea" required maxLength={2000} value={rationale} onChange={(event) => setRationale(event.target.value)} disabled={pending} />
            {actionError !== null && <ErrorState error={actionError} />}
            {saved && <p className="result-panel result-positive" role="status">Resolution recorded by the backend.</p>}
            <button className="button button-primary mt-3" type="submit" disabled={pending || !rationale.trim()}>{pending ? "Saving…" : "Resolve incident"}</button>
          </form>
        )}
      </section>
    </>
  );
}
