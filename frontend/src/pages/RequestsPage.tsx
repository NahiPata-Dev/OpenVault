import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { Badge } from "../components/UI";
import { EmptyState, ErrorState, Loading } from "../components/Feedback";
import { PageHeading, StatusBadge } from "../components/PageHeading";
import { formatIST, formatWindow, statusLabel } from "../lib/format";

interface Booking {
  id: string;
  request_id: string;
  start_at: string;
  end_at: string;
  status: string;
  approved_by: string;
  version: number;
}

interface AccessContract {
  id: string;
  booking_id: string;
  version: number;
  request_id: string;
  resource_id: string;
  requester_id: string;
  approver_id: string;
  start_at: string;
  end_at: string;
  approved_purpose: string;
  policy_version_id: string;
  requirements_snapshot: {
    training_codes?: string[];
    supervisor_required?: boolean;
    supervised_windows?: { weekday: number; start: string; end: string }[];
  };
  status: "ACTIVE" | "COMPLETED" | "CANCELLED";
  expires_at: string;
}

interface RequestRecord {
  id: string;
  requester_id: string;
  resource_id: string;
  purpose: string;
  start_at: string;
  end_at: string;
  status: string;
  created_at: string;
  is_demo: boolean;
}

interface Decision {
  id: string;
  outcome: string;
  explanation: string;
  explanation_code: string;
  created_at: string;
}

interface RequestHistoryItem {
  request: RequestRecord;
  decision: Decision | null;
  booking: Booking | null;
  access_contract: AccessContract | null;
}

interface MyRequestsResponse {
  items: RequestHistoryItem[];
  total: number;
}

interface AuditRecord {
  id: string;
  actor_id: string | null;
  entity_type: string;
  entity_id: string;
  action: string;
  timestamp: string;
  before_summary: Record<string, unknown> | null;
  after_summary: Record<string, unknown> | null;
}

interface ResourceDetail {
  id: string;
  name: string;
  cancellation_cutoff: number;
}

const checklistVersion = "northstar-condition-v1";

function usageInLast30Days(items: RequestHistoryItem[], resourceId: string): number {
  const now = Date.now();
  const lowerBound = now - 30 * 24 * 60 * 60 * 1000;
  return items.reduce((hours, item) => {
    const booking = item.booking;
    if (
      item.request.resource_id !== resourceId ||
      !booking ||
      booking.status === "CANCELLED"
    ) return hours;
    const start = new Date(booking.start_at).getTime();
    if (start < lowerBound || start >= now) return hours;
    return hours + (new Date(booking.end_at).getTime() - start) / 3_600_000;
  }, 0);
}

function DecisionPanel({
  decision,
  request,
  items,
}: {
  decision: Decision;
  request: RequestRecord;
  items: RequestHistoryItem[];
}) {
  const usage = usageInLast30Days(items, request.resource_id);
  return (
    <section className="decision-explanation decision-why" aria-label="Why this decision">
      <div className="card-title-row">
        <h3>Why this decision?</h3>
        <StatusBadge value={decision.outcome} />
      </div>
      <p><strong>Rule applied:</strong> {statusLabel(decision.explanation_code)}</p>
      <p><strong>Reviewer explanation:</strong> {decision.explanation}</p>
      <p><strong>Your recent usage:</strong> {usage.toFixed(1)} hours on this resource in the last 30 days, based on the bookings returned for your account.</p>
      {request.status === "WAITLISTED" && (
        <p><strong>Waitlist position:</strong> The requester API does not include queue position, so it is not shown here.</p>
      )}
      <p className="helper">Usage is shown as context only; the recorded decision and explanation are from the service.</p>
    </section>
  );
}

function ChecklistForm({
  bookingId,
  stage,
  onComplete,
}: {
  bookingId: string;
  stage: "check-in" | "check-out";
  onComplete: () => void;
}) {
  const [physicalCondition, setPhysicalCondition] = useState("ok");
  const [accessoriesComplete, setAccessoriesComplete] = useState("yes");
  const [functionalTest, setFunctionalTest] = useState("works");
  const [notes, setNotes] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [outcome, setOutcome] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setOutcome(null);
    try {
      const result = await api.post<{
        booking: { status: string };
        incident?: { id: string } | null;
      }>(`/bookings/${bookingId}/${stage}`, {
        checklist_version: checklistVersion,
        condition: {
          physical_condition: physicalCondition,
          accessories_complete: accessoriesComplete,
          functional_test: functionalTest,
          notes: notes.trim() || null,
        },
        evidence_references: [],
      });
      setOutcome(
        stage === "check-out"
          ? result.incident
            ? "Return recorded. A condition discrepancy was sent for review; no blame or penalty is assigned."
            : "Return recorded. The service reports no discrepancy."
          : "Check-in recorded by the service.",
      );
      onComplete();
    } catch (submitError) {
      setError(submitError);
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="subform booking-action-form" onSubmit={(event) => void submit(event)}>
      <h3>{stage === "check-in" ? "Check in" : "Check out"}</h3>
      <p className="helper">This versioned checklist records condition and included accessories at handover.</p>
      <div className="form-grid checklist-grid">
        <div>
          <label className="field-label" htmlFor={`${bookingId}-${stage}-condition`}>Physical condition</label>
          <select id={`${bookingId}-${stage}-condition`} className="select" value={physicalCondition} onChange={(event) => setPhysicalCondition(event.target.value)} disabled={pending}>
            <option value="ok">OK</option><option value="minor_wear">Minor wear</option><option value="damaged">Damaged</option>
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor={`${bookingId}-${stage}-accessories`}>Accessories complete</label>
          <select id={`${bookingId}-${stage}-accessories`} className="select" value={accessoriesComplete} onChange={(event) => setAccessoriesComplete(event.target.value)} disabled={pending}>
            <option value="yes">Yes</option><option value="no">No</option>
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor={`${bookingId}-${stage}-functional`}>Functional test</label>
          <select id={`${bookingId}-${stage}-functional`} className="select" value={functionalTest} onChange={(event) => setFunctionalTest(event.target.value)} disabled={pending}>
            <option value="works">Works</option><option value="issue">Issue</option>
          </select>
        </div>
        <div className="checklist-notes">
          <label className="field-label" htmlFor={`${bookingId}-${stage}-notes`}>Notes (optional)</label>
          <textarea id={`${bookingId}-${stage}-notes`} className="textarea" maxLength={2000} value={notes} onChange={(event) => setNotes(event.target.value)} disabled={pending} />
        </div>
      </div>
      {error !== null && <ErrorState error={error} />}
      {outcome && <p className="result-panel result-positive" role="status">{outcome}</p>}
      <button className="button button-primary mt-3" type="submit" disabled={pending}>{pending ? "Saving…" : stage === "check-in" ? "Record check-in" : "Record check-out"}</button>
    </form>
  );
}

function RequestNavigation() {
  return (
    <nav className="request-page-tabs" aria-label="Request and booking pages">
      <Link to="/requests">My requests</Link>
      <Link to="/bookings">My bookings</Link>
    </nav>
  );
}

export function RequestsPage() {
  const [items, setItems] = useState<RequestHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const history = await api.get<MyRequestsResponse>("/requests/mine");
      setItems(history.items);
    } catch (loadError) {
      setError(loadError);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function cancel(requestId: string) {
    setPendingId(requestId);
    setActionError(null);
    try {
      await api.post(`/requests/${requestId}/cancel`);
      await load();
    } catch (cancelError) {
      setActionError(cancelError);
    } finally {
      setPendingId(null);
    }
  }

  const visibleItems = statusFilter === "all" ? items : items.filter((item) => item.request.status === statusFilter);
  return (
    <>
      <PageHeading title="My requests" description="Follow your request decisions and the next step for each one." />
      <RequestNavigation />
      <div className="request-filter-row">
        <label className="field-label" htmlFor="request-status-filter">Filter by status</label>
        <select id="request-status-filter" className="select" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="all">All requests</option>
          {[...new Set(items.map((item) => item.request.status))].sort().map((status) => <option value={status} key={status}>{statusLabel(status)}</option>)}
        </select>
      </div>
      {actionError !== null && <ErrorState error={actionError} />}
      {loading && <Loading label="Loading your requests…" />}
      {error !== null && <ErrorState error={error} />}
      {!loading && error === null && visibleItems.length === 0 && (
        <EmptyState>{items.length ? "No requests match this status." : <>You have not submitted any resource requests yet. <Link to="/resources">Browse resources</Link>.</>}</EmptyState>
      )}
      {!loading && error === null && visibleItems.length > 0 && (
        <div className="request-list">
          {visibleItems.map(({ request, decision, booking, access_contract: contract }) => (
            <article className="request-card" key={request.id}>
              <div className="card-title-row">
                <div><p className="eyebrow">Resource request</p><h2>{statusLabel(request.purpose)}</h2></div>
                <StatusBadge value={request.status} />
              </div>
              {request.is_demo && <Badge>Sample data</Badge>}
              <dl className="request-details">
                <div><dt>Requested window</dt><dd>{formatIST(request.start_at)} – {formatIST(request.end_at)}</dd></div>
                <div><dt>Submitted</dt><dd>{formatIST(request.created_at)}</dd></div>
              </dl>
              {decision && <DecisionPanel decision={decision} request={request} items={items} />}
              {request.status === "INELIGIBLE" && !decision && (
                <section className="decision-explanation"><h3>Eligibility result</h3><p>The request was saved as ineligible. Review the resource requirements and next actions, then submit a new request if circumstances change.</p></section>
              )}
              {contract && booking && (
                <div className="card-actions">
                  <Link className="button button-secondary" to={`/bookings/${booking.id}`}>Booking details</Link>
                  <Link className="button button-secondary" to={`/contracts/${booking.id}`}>Access Contract</Link>
                </div>
              )}
              {!booking && ["PENDING_REVIEW", "WAITLISTED", "INELIGIBLE"].includes(request.status) && (
                <button className="button button-danger" type="button" disabled={pendingId === request.id} onClick={() => void cancel(request.id)}>
                  {pendingId === request.id ? "Cancelling…" : "Cancel request"}
                </button>
              )}
            </article>
          ))}
        </div>
      )}
    </>
  );
}

export function MyBookingsPage() {
  const [items, setItems] = useState<RequestHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    let active = true;
    void api.get<MyRequestsResponse>("/requests/mine").then(
      (result) => active && setItems(result.items.filter((item) => item.booking !== null)),
      (loadError: unknown) => active && setError(loadError),
    ).finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  const statuses = useMemo(() => [...new Set(items.map((item) => item.booking?.status ?? ""))].filter(Boolean).sort(), [items]);
  const visible = statusFilter === "all" ? items : items.filter((item) => item.booking?.status === statusFilter);
  return (
    <>
      <PageHeading title="My bookings" description="Review confirmed sessions, access conditions, and handover actions." />
      <RequestNavigation />
      <div className="request-filter-row">
        <label className="field-label" htmlFor="booking-status-filter">Filter by booking status</label>
        <select id="booking-status-filter" className="select" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="all">All bookings</option>
          {statuses.map((status) => <option value={status} key={status}>{statusLabel(status)}</option>)}
        </select>
      </div>
      {loading && <Loading label="Loading your bookings…" />}
      {error !== null && <ErrorState error={error} />}
      {!loading && error === null && visible.length === 0 && <EmptyState>{items.length ? "No bookings match this status." : <>No bookings are currently attached to your requests. <Link to="/requests">Review my requests</Link>.</>}</EmptyState>}
      {!loading && error === null && visible.length > 0 && (
        <div className="request-list">
          {visible.map(({ request, booking, access_contract: contract }) => booking && (
            <article className="request-card booking-list-card" key={booking.id}>
              <div className="card-title-row"><div><p className="eyebrow">{statusLabel(request.purpose)}</p><h2>Booking</h2></div><StatusBadge value={booking.status} /></div>
              {request.is_demo && <Badge>Sample data</Badge>}
              <dl className="request-details"><div><dt>Session</dt><dd>{formatIST(booking.start_at)} – {formatIST(booking.end_at)}</dd></div><div><dt>Request status</dt><dd>{statusLabel(request.status)}</dd></div><div><dt>Contract</dt><dd>{contract ? `Version ${contract.version}` : "Not returned"}</dd></div></dl>
              <Link className="button button-secondary" to={`/bookings/${booking.id}`}>Open booking details</Link>
            </article>
          ))}
        </div>
      )}
    </>
  );
}

export function BookingDetailPage() {
  const { bookingId = "" } = useParams();
  const [record, setRecord] = useState<RequestHistoryItem | null>(null);
  const [resource, setResource] = useState<ResourceDetail | null>(null);
  const [events, setEvents] = useState<AuditRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [incidentCategory, setIncidentCategory] = useState("other");
  const [incidentDescription, setIncidentDescription] = useState("");
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [incidentPending, setIncidentPending] = useState(false);
  const [cancelPending, setCancelPending] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const mine = await api.get<MyRequestsResponse>("/requests/mine");
      const selected = mine.items.find((item) => item.booking?.id === bookingId) ?? null;
      if (!selected?.booking) {
        setRecord(null);
        setResource(null);
        setEvents([]);
      } else {
        const [resourceResponse, audit] = await Promise.all([
          api.get<{ resource: ResourceDetail }>(`/resources/${selected.request.resource_id}`),
          api.get<{ items: AuditRecord[]; total: number }>(`/audit?entity_type=booking&entity_id=${encodeURIComponent(bookingId)}`),
        ]);
        setRecord(selected);
        setResource(resourceResponse.resource);
        setEvents(audit.items);
      }
    } catch (loadError) {
      setError(loadError);
    } finally {
      setLoading(false);
    }
  }, [bookingId]);

  useEffect(() => { void load(); }, [load]);

  async function cancelRequest() {
    if (!record || !window.confirm("Cancel this request? The service will validate whether cancellation is still allowed.")) return;
    setCancelPending(true);
    setActionError(null);
    try {
      await api.post(`/requests/${record.request.id}/cancel`);
      await load();
    } catch (cancelError) {
      setActionError(cancelError);
    } finally {
      setCancelPending(false);
    }
  }

  async function reportIncident(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!record) return;
    setIncidentPending(true);
    setActionError(null);
    setIncidentId(null);
    try {
      const result = await api.post<{ incident: { id: string } }>(`/bookings/${bookingId}/incidents`, {
        category: incidentCategory,
        description: incidentDescription.trim(),
      });
      setIncidentId(result.incident.id);
      setIncidentDescription("");
      await load();
    } catch (incidentError) {
      setActionError(incidentError);
    } finally {
      setIncidentPending(false);
    }
  }

  if (loading) return <Loading label="Loading booking details…" />;
  if (error !== null) return <ErrorState error={error} />;
  if (!record?.booking) return <EmptyState>This booking is not available in your request history.</EmptyState>;

  const { request, booking, access_contract: contract } = record;
  const canCancel = ["APPROVED", "PENDING_REVIEW", "WAITLISTED", "INELIGIBLE"].includes(request.status)
    && !["CLOSED", "CANCELLED", "INCIDENT_REVIEW"].includes(booking.status);
  const canReportIncident = ["CHECKED_IN", "RETURN_PENDING", "INCIDENT_REVIEW"].includes(booking.status);
  return (
    <>
      <Link className="back-link" to="/bookings">← Back to my bookings</Link>
      <PageHeading title={resource?.name ?? "Booking details"} description={`${statusLabel(request.purpose)} · ${formatIST(booking.start_at)} – ${formatIST(booking.end_at)}`} />
      <div className="card-title-row booking-heading"><StatusBadge value={booking.status} />{request.is_demo && <Badge>Sample data</Badge>}</div>
      {actionError !== null && <ErrorState error={actionError} />}
      {incidentId && <p className="result-panel result-positive" role="status">Incident {incidentId} was reported and recorded by the service.</p>}

      <div className="booking-detail-grid">
        <section className="panel">
          <div className="card-title-row"><h2>Access Contract snapshot</h2>{contract && <Badge>Version {contract.version}</Badge>}</div>
          {contract ? (
            <>
              <p className="contract-note">This snapshot records the session conditions approved for this booking. Later policy edits do not change this record.</p>
              <dl className="request-details">
                <div><dt>Purpose</dt><dd>{contract.approved_purpose}</dd></div>
                <div><dt>Session</dt><dd>{formatIST(contract.start_at)} – {formatIST(contract.end_at)}</dd></div>
                <div><dt>Expires</dt><dd>{formatIST(contract.expires_at)}</dd></div>
                <div><dt>Policy version</dt><dd>{contract.policy_version_id}</dd></div>
                <div><dt>Contract status</dt><dd>{statusLabel(contract.status)}</dd></div>
                <div><dt>Supervision required</dt><dd>{contract.requirements_snapshot.supervisor_required ? "Yes" : "No"}</dd></div>
              </dl>
              <h3>Training snapshot</h3>
              {contract.requirements_snapshot.training_codes?.length ? <ul className="simple-list">{contract.requirements_snapshot.training_codes.map((code) => <li key={code}>{code}</li>)}</ul> : <p>No training requirements were recorded in this snapshot.</p>}
              {contract.requirements_snapshot.supervised_windows?.length ? <ul className="simple-list">{contract.requirements_snapshot.supervised_windows.map((window, index) => <li key={`${window.weekday}-${index}`}>{formatWindow(window)}</li>)}</ul> : null}
            </>
          ) : <p>The service did not return an Access Contract for this booking.</p>}
        </section>
        <section className="panel">
          <h2>Booking timeline</h2>
          {events.length ? (
            <ol className="timeline-list">{[...events].reverse().map((event) => (
              <li className="timeline-item" key={event.id}>
                <time dateTime={event.timestamp}>{formatIST(event.timestamp)}</time>
                <div><strong>{statusLabel(event.action)}</strong><p>Actor ID: {event.actor_id ?? "System"}</p><pre>{JSON.stringify(event.after_summary ?? event.before_summary ?? {}, null, 2)}</pre></div>
              </li>
            ))}</ol>
          ) : <EmptyState>No audit timeline events were returned for this booking.</EmptyState>}
          <p className="helper">The timeline is read from the audit API; it is not editable from this page.</p>
        </section>
      </div>

      <section className="panel booking-actions-panel">
        <h2>Session actions</h2>
        {canCancel && (
          <div className="booking-action">
            <h3>Cancel request</h3>
            <p className="helper">Cancellation is subject to the resource cutoff ({resource?.cancellation_cutoff ?? 2} hours before the start). The service enforces the final rule.</p>
            <button type="button" className="button button-danger" disabled={cancelPending} onClick={() => void cancelRequest()}>{cancelPending ? "Cancelling…" : "Cancel request"}</button>
          </div>
        )}
        {["CONFIRMED", "NO_SHOW"].includes(booking.status) && <ChecklistForm bookingId={bookingId} stage="check-in" onComplete={() => void load()} />}
        {booking.status === "CHECKED_IN" && <ChecklistForm bookingId={bookingId} stage="check-out" onComplete={() => void load()} />}
        {!canCancel && !["CONFIRMED", "NO_SHOW", "CHECKED_IN"].includes(booking.status) && <p className="muted">No session action is currently available for this booking state.</p>}
        {canReportIncident && (
          <form className="subform booking-action-form" onSubmit={(event) => void reportIncident(event)}>
            <h3>Report an incident</h3>
            <p className="helper">Reports are stored for review. The system does not assign blame or apply a penalty.</p>
            <label className="field-label" htmlFor="incident-category">Category</label>
            <select id="incident-category" className="select" value={incidentCategory} onChange={(event) => setIncidentCategory(event.target.value)}>
              {["damage", "missing_part", "malfunction", "late_return", "other"].map((category) => <option value={category} key={category}>{statusLabel(category)}</option>)}
            </select>
            <label className="field-label mt-4" htmlFor="incident-description">What happened?</label>
            <textarea id="incident-description" className="textarea" required maxLength={4000} value={incidentDescription} onChange={(event) => setIncidentDescription(event.target.value)} />
            <button className="button button-primary mt-3" type="submit" disabled={incidentPending || !incidentDescription.trim()}>{incidentPending ? "Reporting…" : "Submit incident report"}</button>
          </form>
        )}
      </section>
    </>
  );
}

export function ContractPage() {
  const { bookingId = "" } = useParams();
  const [record, setRecord] = useState<RequestHistoryItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    void api.get<MyRequestsResponse>("/requests/mine").then(
      (result) => active && setRecord(result.items.find((item) => item.booking?.id === bookingId) ?? null),
      (loadError: unknown) => active && setError(loadError),
    ).finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [bookingId]);

  if (loading) return <Loading label="Loading access conditions…" />;
  if (error !== null) return <ErrorState error={error} />;
  if (!record?.access_contract) return <EmptyState>No access contract was returned for this booking.</EmptyState>;

  const contract = record.access_contract;
  const requirements = contract.requirements_snapshot;
  return (
    <>
      <Link className="back-link" to={`/bookings/${bookingId}`}>← Back to booking details</Link>
      <PageHeading title="Access Contract (session conditions)" description={`Version ${contract.version} · ${contract.status}`} />
      <div className="panel contract-panel">
        <p className="contract-note">This is an application record of the session conditions, not a legal contract.</p>
        <dl className="request-details">
          <div><dt>Purpose</dt><dd>{contract.approved_purpose}</dd></div>
          <div><dt>Session</dt><dd>{formatIST(contract.start_at)} – {formatIST(contract.end_at)}</dd></div>
          <div><dt>Expires</dt><dd>{formatIST(contract.expires_at)}</dd></div>
          <div><dt>Resource</dt><dd>{contract.resource_id}</dd></div>
          <div><dt>Policy version</dt><dd>{contract.policy_version_id}</dd></div>
          <div><dt>Check-in required</dt><dd>Yes</dd></div>
          <div><dt>Check-out required</dt><dd>Yes</dd></div>
        </dl>
        <h2>Requirements snapshot</h2>
        {requirements.training_codes?.length ? <ul className="simple-list">{requirements.training_codes.map((code) => <li key={code}>{code}</li>)}</ul> : <p>No training requirements were recorded in this snapshot.</p>}
        <p>Supervision required: {requirements.supervisor_required ? "Yes" : "No"}</p>
        {requirements.supervised_windows?.length ? <ul className="simple-list">{requirements.supervised_windows.map((window, index) => <li key={`${window.weekday}-${index}`}>{formatWindow(window)}</li>)}</ul> : null}
      </div>
    </>
  );
}
