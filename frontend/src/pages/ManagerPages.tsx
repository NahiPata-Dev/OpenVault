import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { DemoAccount } from "../api/types";
import { Badge, Button, Modal, Toast, useToast } from "../components/UI";
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
  is_demo?: boolean;
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
  const [statusFilter, setStatusFilter] = useState("all");
  const [resourceFilter, setResourceFilter] = useState("all");
  const [sortOrder, setSortOrder] = useState("newest");
  const [confirming, setConfirming] = useState<{ requestId: string; outcome: string } | null>(null);

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

  function decide(event: FormEvent<HTMLFormElement>, requestId: string) {
    event.preventDefault();
    const outcome = (event.nativeEvent as SubmitEvent).submitter;
    if (!(outcome instanceof HTMLButtonElement)) return;
    if (!reasons[requestId]?.trim()) return;
    setConfirming({ requestId, outcome: outcome.value });
  }

  async function confirmDecision() {
    if (!confirming) return;
    const { requestId, outcome } = confirming;
    const reason = reasons[requestId]?.trim() ?? "";
    if (!reason) return;
    setPendingId(requestId);
    setActionError(null);
    try {
      await api.post(`/requests/${requestId}/decision`, {
        outcome,
        reason,
        override_reason: null,
      });
      setReasons((current) => ({ ...current, [requestId]: "" }));
      setConfirming(null);
      await load();
    } catch (decisionError) {
      setActionError(decisionError);
    } finally {
      setPendingId(null);
    }
  }

  const resourceIds = [...new Set(items.map(({ request }) => request.resource_id))];
  const filteredItems = items.filter(({ request }) =>
    (statusFilter === "all" || request.status === statusFilter)
    && (resourceFilter === "all" || request.resource_id === resourceFilter),
  ).sort((left, right) => {
    const direction = sortOrder === "oldest" ? 1 : -1;
    return direction * (new Date(left.request.created_at).getTime() - new Date(right.request.created_at).getTime());
  });

  return (
    <>
      <PageHeading
        title="Manager queue"
        description="Review eligibility and allocation guidance. Recommendations do not make decisions."
      />
      {actionError !== null && <ErrorState error={actionError} />}
      <section className="panel queue-filters" aria-label="Request queue filters">
        <div>
          <label className="field-label" htmlFor="queue-status">Status</label>
          <select id="queue-status" className="select" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">All statuses</option><option value="PENDING_REVIEW">Pending review</option><option value="WAITLISTED">Waitlisted</option><option value="APPROVED">Approved</option><option value="REJECTED">Rejected</option>
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor="queue-resource">Resource</label>
          <select id="queue-resource" className="select" value={resourceFilter} onChange={(event) => setResourceFilter(event.target.value)}>
            <option value="all">All resources</option>{resourceIds.map((id) => <option value={id} key={id}>{resources.get(id) ?? id}</option>)}
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor="queue-sort">Sort by submission date</label>
          <select id="queue-sort" className="select" value={sortOrder} onChange={(event) => setSortOrder(event.target.value)}>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
        </div>
      </section>
      {loading && <Loading label="Loading the manager queue…" />}
      {error !== null && <ErrorState error={error} />}
      {!loading && error === null && filteredItems.length === 0 && <EmptyState>{items.length === 0 ? "No requests are visible in your manager queue." : "No requests match these filters."}</EmptyState>}
      {!loading && error === null && filteredItems.length > 0 && (
        <div className="request-list">
          {filteredItems.map(({ request, eligibility, allocation_recommendation: recommendation }) => {
            const snapshot = recommendation.inputs_snapshot;
            const candidate = snapshot.candidates.find((row) => row.request_id === request.id);
            const competitors = items.filter((item) =>
              item.request.resource_id === request.resource_id
              && item.request.start_at === request.start_at
              && item.request.end_at === request.end_at,
            );
            return (
              <article className="request-card" key={request.id}>
                <div className="card-title-row">
                  <div>
                    <p className="eyebrow">{resources.get(request.resource_id) ?? "Resource"}</p>
                    <h2>{statusLabel(request.purpose)}</h2>
                  </div>
                  <StatusBadge value={request.status} />
                </div>
                {request.is_demo && <Badge>Sample data</Badge>}
                <dl className="request-details">
                  <div><dt>Requester</dt><dd>{users.get(request.requester_id) ?? `Account ${request.requester_id}`}</dd></div>
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
                {competitors.length > 1 && <section className="competing-requests">
                  <h3>Competing requests for this slot</h3>
                  <div className="comparison-grid">{competitors.map((other) => {
                    const contender = other.allocation_recommendation.inputs_snapshot.candidates.find((row) => row.request_id === other.request.id);
                    return <article className="comparison-card" key={other.request.id}>
                      <strong>{users.get(other.request.requester_id) ?? `Account ${other.request.requester_id}`}</strong>
                      <p>{statusLabel(other.request.status)} · {statusLabel(other.request.purpose)}</p>
                      <p>{other.eligibility.eligible ? "Eligible" : `${other.eligibility.blockers.length} eligibility blocker(s)`}</p>
                      <p>{contender ? `${contender.completed_bookings_30d} completed sessions · ${contender.booked_hours_30d} hours / 30 days` : "Usage details unavailable"}</p>
                      <p>Recommendation: {statusLabel(other.allocation_recommendation.recommendation)}</p>
                    </article>;
                  })}</div>
                </section>}
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
                {confirming && <div className="modal-backdrop" role="presentation">
                  <section className="confirmation-modal" role="dialog" aria-modal="true" aria-labelledby="decision-confirm-title">
                    <h2 id="decision-confirm-title">Confirm {statusLabel(confirming.outcome)} decision</h2>
                    <p>This records the decision and written reason in the backend audit history.</p>
                    <blockquote>{reasons[confirming.requestId]}</blockquote>
                    {actionError !== null && <ErrorState error={actionError} />}
                    <div className="card-actions">
                      <button type="button" className="button button-primary" disabled={pendingId === confirming.requestId} onClick={() => void confirmDecision()}>{pendingId === confirming.requestId ? "Saving…" : "Confirm decision"}</button>
                      <button type="button" className="button button-secondary" disabled={pendingId === confirming.requestId} onClick={() => setConfirming(null)}>Cancel</button>
                    </div>
                  </section>
                </div>}
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
      <PageHeading title="Training sign-off" description="Append a verified training record for a user in your organization. Existing records are not overwritten." />
      <p className="helper">The current API accepts valid, expired or revoked training records. It does not expose a history list or persist an auditable reason for an extension or revocation; those controls are not simulated here.</p>
      <p className="helper">The current user selector is limited to seeded accounts because no manager-scoped user directory endpoint is available.</p>
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
  const [response, setResponse] = useState("");
  const [reviewReason, setReviewReason] = useState("");
  const [resolveConfirmationOpen, setResolveConfirmationOpen] = useState(false);
  const toast = useToast();

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

  async function resolve() {
    setPending(true);
    setActionError(null);
    setSaved(false);
    try {
      await api.post(`/incidents/${incidentId}/resolve`, { outcome, rationale: rationale.trim() });
      setSaved(true);
      setResolveConfirmationOpen(false);
      toast.show("Incident resolution recorded.");
      await load();
    } catch (resolveError) {
      setActionError(resolveError);
    } finally {
      setPending(false);
    }
  }

  async function addResponse(event: FormEvent<HTMLFormElement>) {
      event.preventDefault();
      setPending(true);
      setActionError(null);
      try {
        await api.post(`/incidents/${incidentId}/responses`, { message: response.trim() });
        setResponse("");
        await load();
      } catch (responseError) {
        setActionError(responseError);
      } finally {
        setPending(false);
      }
  }

  async function review(status: "under_review" | "information_requested") {
      setPending(true);
      setActionError(null);
      try {
        await api.post(`/incidents/${incidentId}/review`, { status, reason: reviewReason.trim() });
        setReviewReason("");
        await load();
      } catch (reviewError) {
        setActionError(reviewError);
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
          <>
          <form className="decision-form" onSubmit={(event) => void addResponse(event)}>
            <h3>Add a response</h3>
            <label className="field-label" htmlFor="incident-response">Response</label>
            <textarea id="incident-response" className="textarea" required maxLength={2000} value={response} onChange={(event) => setResponse(event.target.value)} disabled={pending} />
            <button className="button button-secondary" type="submit" disabled={pending || !response.trim()}>Add response</button>
          </form>
          <form className="decision-form" onSubmit={(event) => { event.preventDefault(); void review("under_review"); }}>
            <h3>Review status</h3>
            <label className="field-label" htmlFor="incident-review-reason">Review reason (required)</label>
            <textarea id="incident-review-reason" className="textarea" required maxLength={2000} value={reviewReason} onChange={(event) => setReviewReason(event.target.value)} disabled={pending} />
            <div className="card-actions">
              <button className="button button-secondary" type="submit" disabled={pending || !reviewReason.trim()}>Begin review</button>
              <button className="button button-secondary" type="button" disabled={pending || !reviewReason.trim()} onClick={() => void review("information_requested")}>Request information</button>
            </div>
          </form>
          {incident.status === "UNDER_REVIEW" && <form className="decision-form" onSubmit={(event) => {
            event.preventDefault();
            setResolveConfirmationOpen(true);
          }}>
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
            <button className="button button-primary mt-3" type="submit" disabled={pending || !rationale.trim()}>Resolve incident</button>
          </form>}
          {incident.status !== "UNDER_REVIEW" && <p className="helper">Move this incident to “Under review” before recording a resolution or dismissal.</p>}
          </>
        )}
        {actionError !== null && <ErrorState error={actionError} />}
        <p className="helper">Incident handling records facts and a human rationale. Nothing is penalized automatically.</p>
      </section>
      <Modal open={resolveConfirmationOpen} title="Confirm incident resolution" onClose={() => {
        if (!pending) setResolveConfirmationOpen(false);
      }}>
        <p>Record this outcome and rationale in the incident history?</p>
        <p><strong>Outcome:</strong> {statusLabel(outcome)}</p>
        <blockquote>{rationale}</blockquote>
        {actionError !== null && <ErrorState error={actionError} />}
        <div className="card-actions">
          <Button type="button" disabled={pending} onClick={() => void resolve()}>{pending ? "Saving…" : "Confirm resolution"}</Button>
          <Button type="button" variant="secondary" disabled={pending} onClick={() => setResolveConfirmationOpen(false)}>Go back</Button>
        </div>
      </Modal>
      <Toast message={toast.message} onDismiss={toast.dismiss} />
    </>
  );
}

interface ManagerDashboardItem {
  id: string;
  type: string;
  title: string;
  at: string | null;
  status: string;
}

export function ManagerSessionsPage() {
  const [items, setItems] = useState<ManagerDashboardItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    void api.get<{ next_items: ManagerDashboardItem[] }>("/dashboard/manager")
      .then((result) => active && setItems(result.next_items.filter((item) => item.type === "upcoming_booking")))
      .catch((loadError: unknown) => active && setError(loadError))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  const dateInIST = (value: string) => new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
  const today = dateInIST(new Date().toISOString());
  const todayItems = items.filter((item) => item.at && dateInIST(item.at) === today);
  const upcoming = items.filter((item) => item.at && dateInIST(item.at) > today);

  return (
    <>
      <PageHeading title="Sessions" description="Upcoming sessions returned by the manager dashboard." />
      <p className="helper">The current API exposes at most five mixed dashboard items and has no manager booking-detail or handover-report endpoint. Condition comparisons and the complete session history cannot be loaded here.</p>
      {loading && <Loading label="Loading upcoming sessions…" />}
      {error !== null && <ErrorState error={error} />}
      {!loading && error === null && items.length === 0 && <EmptyState>No upcoming sessions were present in the dashboard response.</EmptyState>}
      {!loading && error === null && items.length > 0 && <>
        <section className="memory-section">
          <h2>Today</h2>
          {todayItems.length === 0 ? <EmptyState>No sessions today in the returned items.</EmptyState> : <div className="request-list">{todayItems.map((item) => (
            <article className="request-card" key={item.id}>
              <div className="card-title-row"><h3>{item.title}</h3><StatusBadge value={item.status} /></div>
              <p>{item.at ? formatIST(item.at) : "Time unavailable"}</p><p className="muted">Booking ID: {item.id}</p>
            </article>
          ))}</div>}
        </section>
        <section className="memory-section">
          <h2>Upcoming</h2>
          {upcoming.length === 0 ? <EmptyState>No future sessions in the returned items.</EmptyState> : <div className="request-list">{upcoming.map((item) => (
            <article className="request-card" key={item.id}>
              <div className="card-title-row"><h3>{item.title}</h3><StatusBadge value={item.status} /></div>
              <p>{item.at ? formatIST(item.at) : "Time unavailable"}</p><p className="muted">Booking ID: {item.id}</p>
            </article>
          ))}</div>}
        </section>
        <section className="panel">
          <h2>Check-in and check-out records</h2>
          <p>These are requester-only API actions. No handover condition records are exposed to managers in the current API.</p>
        </section>
      </>}
    </>
  );
}
