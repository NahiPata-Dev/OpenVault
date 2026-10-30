import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { EmptyState, ErrorState, Loading } from "../components/Feedback";
import { PageHeading, StatusBadge } from "../components/PageHeading";
import { formatIST, statusLabel } from "../lib/format";

interface ResourceSummary {
  id: string;
  name: string;
}

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

interface ResourceListResponse {
  items: ResourceSummary[];
  total: number;
}

const checklistVersion = "northstar-condition-v1";

interface ChecklistFormProps {
  bookingId: string;
  stage: "check-in" | "check-out";
  onComplete: () => void;
}

function ChecklistForm({ bookingId, stage, onComplete }: ChecklistFormProps) {
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
            ? "The check-out recorded a discrepancy and opened an incident for review. No blame or penalty is assigned."
            : "Check-out recorded. The backend reports that no discrepancy was found."
          : "Check-in recorded by the backend.",
      );
      onComplete();
    } catch (submitError) {
      setError(submitError);
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="subform" onSubmit={(event) => void submit(event)}>
      <h3>{stage === "check-in" ? "Check in" : "Check out"}</h3>
      <div className="form-grid checklist-grid">
        <div>
          <label className="field-label" htmlFor={`${bookingId}-${stage}-condition`}>Physical condition</label>
          <select
            id={`${bookingId}-${stage}-condition`}
            className="select"
            value={physicalCondition}
            onChange={(event) => setPhysicalCondition(event.target.value)}
            disabled={pending}
          >
            <option value="ok">OK</option>
            <option value="minor_wear">Minor wear</option>
            <option value="damaged">Damaged</option>
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor={`${bookingId}-${stage}-accessories`}>Accessories complete</label>
          <select
            id={`${bookingId}-${stage}-accessories`}
            className="select"
            value={accessoriesComplete}
            onChange={(event) => setAccessoriesComplete(event.target.value)}
            disabled={pending}
          >
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor={`${bookingId}-${stage}-functional`}>Functional test</label>
          <select
            id={`${bookingId}-${stage}-functional`}
            className="select"
            value={functionalTest}
            onChange={(event) => setFunctionalTest(event.target.value)}
            disabled={pending}
          >
            <option value="works">Works</option>
            <option value="issue">Issue</option>
          </select>
        </div>
        <div className="checklist-notes">
          <label className="field-label" htmlFor={`${bookingId}-${stage}-notes`}>Notes (optional)</label>
          <textarea
            id={`${bookingId}-${stage}-notes`}
            className="textarea"
            maxLength={2000}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            disabled={pending}
          />
        </div>
      </div>
      {error !== null && <ErrorState error={error} />}
      {outcome && <p className="result-panel result-positive" role="status">{outcome}</p>}
      <button className="button button-primary mt-3" type="submit" disabled={pending}>
        {pending ? "Submitting…" : stage === "check-in" ? "Record check-in" : "Record check-out"}
      </button>
    </form>
  );
}

export function RequestsPage() {
  const [items, setItems] = useState<RequestHistoryItem[]>([]);
  const [resources, setResources] = useState<Map<string, string>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [history, resourceList] = await Promise.all([
        api.get<MyRequestsResponse>("/requests/mine"),
        api.get<ResourceListResponse>("/resources"),
      ]);
      setItems(history.items);
      setResources(new Map(resourceList.items.map((resource) => [resource.id, resource.name])));
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

  return (
    <>
      <PageHeading
        title="My requests"
        description="Track request decisions, access conditions, and handovers."
      />
      {actionError !== null && <ErrorState error={actionError} />}
      {loading && <Loading label="Loading your requests…" />}
      {error !== null && <ErrorState error={error} />}
      {!loading && error === null && items.length === 0 && (
        <EmptyState>You have not submitted any resource requests yet. <Link to="/resources">Browse resources</Link>.</EmptyState>
      )}
      {!loading && error === null && items.length > 0 && (
        <div className="request-list">
          {items.map(({ request, decision, booking, access_contract: contract }) => (
            <article className="request-card" key={request.id}>
              <div className="card-title-row">
                <div>
                  <p className="eyebrow">{resources.get(request.resource_id) ?? "Resource request"}</p>
                  <h2>{statusLabel(request.purpose)}</h2>
                </div>
                <StatusBadge value={request.status} />
              </div>
              <dl className="request-details">
                <div><dt>Requested</dt><dd>{formatIST(request.start_at)} – {formatIST(request.end_at)}</dd></div>
                <div><dt>Submitted</dt><dd>{formatIST(request.created_at)}</dd></div>
              </dl>
              {decision && (
                <div className="decision-explanation">
                  <p><strong>Decision: {statusLabel(decision.outcome)}</strong> · {formatIST(decision.created_at)}</p>
                  <p>{decision.explanation}</p>
                </div>
              )}
              {request.status === "INELIGIBLE" && !decision && (
                <p className="decision-explanation">This request is ineligible according to the backend’s current readiness result.</p>
              )}
              {contract && booking && (
                <div className="card-actions">
                  <Link className="button button-secondary" to={`/contracts/${booking.id}`}>View Access Contract</Link>
                </div>
              )}
              {booking && (
                <section className="booking-handover" aria-label="Booking check-in and check-out">
                  <div className="card-title-row">
                    <h3>Booking handover</h3>
                    <StatusBadge value={booking.status} />
                  </div>
                  {request.status === "APPROVED" && (
                    <p className="helper">
                      {Date.now() > new Date(request.start_at).getTime() - 2 * 60 * 60 * 1000
                        ? "Cancellation is closed less than two hours before start."
                        : "Cancellation is allowed until two hours before start. The backend enforces this cutoff."}
                    </p>
                  )}
                  {request.status !== "APPROVED" && Date.now() > new Date(request.start_at).getTime() - 2 * 60 * 60 * 1000 && (
                    <p className="helper">Cancellation is closed less than two hours before start.</p>
                  )}
                  {["APPROVED", "PENDING_REVIEW", "WAITLISTED", "INELIGIBLE"].includes(request.status)
                    && !(request.status === "APPROVED" && Date.now() > new Date(request.start_at).getTime() - 2 * 60 * 60 * 1000) && (
                    <button className="button button-danger" type="button" disabled={pendingId === request.id} onClick={() => void cancel(request.id)}>
                      {pendingId === request.id ? "Cancelling…" : "Cancel request"}
                    </button>
                  )}
                  {booking.status === "CONFIRMED" || booking.status === "NO_SHOW" ? (
                    <ChecklistForm key={`${booking.id}-check-in`} bookingId={booking.id} stage="check-in" onComplete={() => void load()} />
                  ) : null}
                  {booking.status === "CHECKED_IN" ? (
                    <ChecklistForm key={`${booking.id}-check-out`} bookingId={booking.id} stage="check-out" onComplete={() => void load()} />
                  ) : null}
                  {["CLOSED", "INCIDENT_REVIEW"].includes(booking.status) && (
                    <p className="helper">The backend reports this booking as {statusLabel(booking.status)}. Review or incident information is shown when available.</p>
                  )}
                </section>
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

export function ContractPage() {
  const { bookingId = "" } = useParams();
  return <ContractPageContent bookingId={bookingId} />;
}

function ContractPageContent({ bookingId }: { bookingId: string }) {
  const [record, setRecord] = useState<RequestHistoryItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    void api.get<MyRequestsResponse>("/requests/mine").then(
      (result) => {
        if (active) setRecord(result.items.find((item) => item.booking?.id === bookingId) ?? null);
      },
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
      <Link className="back-link" to="/requests">← Back to my requests</Link>
      <PageHeading
        title="Access Contract (session conditions)"
        description={`Version ${contract.version} · ${contract.status}`}
      />
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
        {requirements.training_codes?.length ? (
          <ul className="simple-list">{requirements.training_codes.map((code) => <li key={code}>{code}</li>)}</ul>
        ) : <p>No training requirements were recorded in this snapshot.</p>}
        <p>Supervision required: {requirements.supervisor_required ? "Yes" : "No"}</p>
        {requirements.supervised_windows && requirements.supervised_windows.length > 0 && (
          <ul className="simple-list">
            {requirements.supervised_windows.map((window, index) => <li key={`${window.weekday}-${index}`}>{["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][window.weekday - 1]} · {window.start}–{window.end} IST</li>)}
          </ul>
        )}
      </div>
    </>
  );
}
