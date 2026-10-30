import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { EmptyState, ErrorState, Loading } from "../components/Feedback";
import { PageHeading, StatusBadge } from "../components/PageHeading";
import { formatIST, istDateEndToISO, istInputToISO } from "../lib/format";

interface Resource {
  id: string;
  name: string;
}

interface TimelineEvent {
  timestamp: string;
  event: string;
  actor: string | null;
  summary: Record<string, unknown>;
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

export function AuditTimelinePage() {
  const [resources, setResources] = useState<Resource[]>([]);
  const [resourceId, setResourceId] = useState("");
  const [bookingId, setBookingId] = useState("");
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [bookingEvents, setBookingEvents] = useState<AuditRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [queryLoading, setQueryLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [queryError, setQueryError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    void api.get<{ items: Resource[]; total: number }>("/resources").then((response) => {
      if (!active) return;
      setResources(response.items);
      setResourceId(response.items[0]?.id ?? "");
    }).catch((loadError: unknown) => active && setError(loadError))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!resourceId) return;
    let active = true;
    setQueryLoading(true);
    setQueryError(null);
    void api.get<{ items: TimelineEvent[] }>(`/resources/${resourceId}/timeline`).then((result) => {
      if (active) setTimeline(result.items);
    }).catch((loadError: unknown) => active && setQueryError(loadError))
      .finally(() => active && setQueryLoading(false));
    return () => { active = false; };
  }, [resourceId]);

  async function loadBooking(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQueryLoading(true);
    setQueryError(null);
    try {
      const params = new URLSearchParams({ entity_type: "booking", entity_id: bookingId.trim() });
      const response = await api.get<{ items: AuditRecord[]; total: number }>(`/audit?${params.toString()}`);
      setBookingEvents(response.items);
    } catch (loadError) {
      setQueryError(loadError);
      setBookingEvents([]);
    } finally {
      setQueryLoading(false);
    }
  }

  return (
    <>
      <PageHeading title="Audit timeline" description="Read-only history from the backend, scoped to your role." />
      {loading && <Loading label="Loading resources…" />}
      {error !== null && <ErrorState error={error} />}
      {!loading && error === null && (
        <>
          {resources.length === 0 && <EmptyState>No resources are available for an audit timeline.</EmptyState>}
          <section className="panel timeline-controls">
            <label className="field-label" htmlFor="audit-resource">Resource timeline</label>
            <select id="audit-resource" className="select" value={resourceId} onChange={(event) => setResourceId(event.target.value)}>
              {resources.map((resource) => <option value={resource.id} key={resource.id}>{resource.name}</option>)}
            </select>
          </section>
          {queryError !== null && <ErrorState error={queryError} />}
          {queryLoading && <Loading label="Loading audit history…" />}
          {!queryLoading && queryError === null && (
            <section className="timeline-section">
              <h2>Resource events</h2>
              {timeline.length === 0 ? <EmptyState>No resource events were returned.</EmptyState> : (
                <ol className="timeline-list">
                  {timeline.map((event, index) => (
                    <li key={`${event.timestamp}-${event.event}-${index}`} className="timeline-item">
                      <time>{formatIST(event.timestamp)}</time>
                      <div>
                        <strong>{event.event}</strong>
                        <p>Actor: {event.actor ?? "System"}</p>
                        <pre>{JSON.stringify(event.summary, null, 2)}</pre>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          )}
          <section className="panel booking-audit-panel">
            <h2>Booking events</h2>
            <p className="helper">Enter a booking ID to request its scoped audit trail. The backend verifies access.</p>
            <form className="booking-id-form" onSubmit={(event) => void loadBooking(event)}>
              <div>
                <label className="field-label" htmlFor="audit-booking-id">Booking ID</label>
                <input id="audit-booking-id" className="input" required value={bookingId} onChange={(event) => setBookingId(event.target.value)} />
              </div>
              <button className="button button-primary" type="submit" disabled={queryLoading || !bookingId.trim()}>Load booking timeline</button>
            </form>
            {bookingEvents.length === 0 && bookingId && !queryLoading && queryError === null && (
              <EmptyState>No booking events have been returned for this ID.</EmptyState>
            )}
            {bookingEvents.length > 0 && (
              <ol className="timeline-list">
                {bookingEvents.map((event) => (
                  <li key={event.id} className="timeline-item">
                    <time>{formatIST(event.timestamp)}</time>
                    <div>
                      <strong>{event.action}</strong>
                      <p>Actor ID: {event.actor_id ?? "System"} · Entity: {event.entity_type}</p>
                      <pre>{JSON.stringify(event.after_summary ?? event.before_summary ?? {}, null, 2)}</pre>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </>
      )}
    </>
  );
}

interface Metrics {
  available_hours: number;
  scheduled_hours: number;
  completed_hours: number;
  cancellations: number;
  no_shows: number;
  blocked_hours_by_reason: Record<string, number>;
  waitlist_demand: { requests: number; hours: number };
  maintenance_holds: { count: number; hours: number };
  unresolved_incidents: number;
}

interface Recommendation {
  recommendation_code: string;
  text: string;
  trigger_rule: string;
  source_counts: Record<string, number>;
  range_start: string;
  range_end: string;
  limitations: string[];
  demo_data: boolean;
}

interface ResourceMemory {
  resource_id: string;
  range: { from: string; to: string };
  metrics: Metrics;
  recommendations: Recommendation[];
  demo_data: boolean;
  label: string | null;
}

export function ResourceMemoryPage() {
  const { resourceId = "" } = useParams();
  const [resource, setResource] = useState<Resource | null>(null);
  const [memory, setMemory] = useState<ResourceMemory | null>(null);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  const load = useCallback(async (from?: string, to?: string) => {
    setPending(true);
    setError(null);
    try {
      const query = new URLSearchParams();
      if (from && to) {
        query.set("from", istInputToISO(`${from}T00:00`));
        query.set("to", istDateEndToISO(to));
      }
      const [detail, report] = await Promise.all([
        api.get<{ resource: Resource }>(`/resources/${resourceId}`),
        api.get<ResourceMemory>(`/resources/${resourceId}/memory${query.size ? `?${query}` : ""}`),
      ]);
      setResource(detail.resource);
      setMemory(report);
    } catch (loadError) {
      setError(loadError);
    } finally {
      setLoading(false);
      setPending(false);
    }
  }, [resourceId]);

  useEffect(() => { void load(); }, [load]);

  function applyRange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!fromDate || !toDate) return;
    void load(fromDate, toDate);
  }

  if (loading) return <Loading label="Loading resource memory…" />;
  if (error !== null) return <ErrorState error={error} />;
  if (!memory || !resource) return <EmptyState>Resource memory is not available.</EmptyState>;

  return (
    <>
      <Link className="back-link" to={`/resources/${resourceId}`}>← Back to resource</Link>
      <PageHeading title={`Resource Memory · ${resource.name}`} description="Metrics and planning recommendations from persisted backend records." />
      {memory.demo_data && <p className="memory-demo-label" role="note">{memory.label ?? "DEMO DATA — not live institutional statistics"}</p>}
      <section className="panel memory-range">
        <p><strong>Current range:</strong> {formatIST(memory.range.from)} – {formatIST(memory.range.to)}</p>
        <form className="range-form" onSubmit={applyRange}>
          <div>
            <label className="field-label" htmlFor="memory-from">From date (IST)</label>
            <input id="memory-from" className="input" type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} />
          </div>
          <div>
            <label className="field-label" htmlFor="memory-to">To date (IST)</label>
            <input id="memory-to" className="input" type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} />
          </div>
          <button className="button button-primary" type="submit" disabled={pending || !fromDate || !toDate}>Apply date range</button>
        </form>
        {Boolean(fromDate) !== Boolean(toDate) && <p className="helper">Choose both dates to apply a range. The default is the last 30 days.</p>}
        {pending && <Loading label="Updating resource memory…" />}
      </section>
      <section className="memory-section">
        <h2>Metrics</h2>
        {memory.demo_data && <p className="memory-inline-label">DEMO DATA</p>}
        <dl className="metric-grid">
          <Metric label="Available hours" value={memory.metrics.available_hours} />
          <Metric label="Scheduled hours" value={memory.metrics.scheduled_hours} />
          <Metric label="Completed hours" value={memory.metrics.completed_hours} />
          <Metric label="Cancellations" value={memory.metrics.cancellations} />
          <Metric label="No-shows" value={memory.metrics.no_shows} />
          <Metric label="Unresolved incidents" value={memory.metrics.unresolved_incidents} />
          <Metric label="Waitlist requests" value={memory.metrics.waitlist_demand.requests} detail={`${memory.metrics.waitlist_demand.hours} hours`} />
          <Metric label="Maintenance holds" value={memory.metrics.maintenance_holds.count} detail={`${memory.metrics.maintenance_holds.hours} hours`} />
        </dl>
        <article className="panel blocked-hours">
          <h3>Blocked hours by reason</h3>
          {Object.keys(memory.metrics.blocked_hours_by_reason).length === 0 ? <p className="muted">No blocked hours reported in this range.</p> : (
            <ul className="metric-reasons">
              {Object.entries(memory.metrics.blocked_hours_by_reason).map(([reason, hours]) => <li key={reason}><span>{reason}</span><strong>{hours} hours</strong></li>)}
            </ul>
          )}
        </article>
      </section>
      <section className="memory-section">
        <h2>Recommendations</h2>
        {memory.demo_data && <p className="memory-inline-label">DEMO DATA</p>}
        {memory.recommendations.length === 0 ? <EmptyState>No recommendations were triggered for this resource and range.</EmptyState> : (
          <div className="recommendation-list">
            {memory.recommendations.map((recommendation) => (
              <article className="panel recommendation-card" key={recommendation.recommendation_code}>
                <div className="card-title-row">
                  <h3>{recommendation.recommendation_code.replaceAll("_", " ")}</h3>
                  {recommendation.demo_data && <StatusBadge value="DEMO DATA" />}
                </div>
                <p>{recommendation.text}</p>
                <p className="helper"><strong>Trigger:</strong> {recommendation.trigger_rule}</p>
                <p className="helper"><strong>Date range:</strong> {formatIST(recommendation.range_start)} – {formatIST(recommendation.range_end)}</p>
                <h4>Source counts</h4>
                <ul className="metric-reasons">
                  {Object.entries(recommendation.source_counts).map(([key, value]) => <li key={key}><span>{key.replaceAll("_", " ")}</span><strong>{value}</strong></li>)}
                </ul>
                {recommendation.limitations.length > 0 && <p className="helper">Limitations: {recommendation.limitations.join(" ")}</p>}
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function Metric({ label, value, detail }: { label: string; value: number; detail?: string }) {
  return (
    <div className="metric-card">
      <dt>{label}</dt>
      <dd>{value}{detail && <span>{detail}</span>}</dd>
    </div>
  );
}

interface ResetResponse {
  ok: boolean;
  reset_counts: { resources: number; requests: number; bookings: number; incidents: number };
}

export function AdminPage() {
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<ResetResponse | null>(null);

  async function reset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.post<ResetResponse>("/admin/demo-reset", { confirmation }));
      setConfirmation("");
    } catch (resetError) {
      setError(resetError);
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <PageHeading title="Administration" description="Restricted demo data maintenance." />
      <section className="panel admin-panel">
        <h2>Reset seeded demo data</h2>
        <p>This action replaces seeded demo records. It does not reset non-demo records. Only the institution administrator can request this; the backend enforces demo-environment restrictions.</p>
        <form onSubmit={(event) => void reset(event)}>
          <label className="field-label" htmlFor="reset-confirmation">Type RESET_DEMO_DATA to confirm</label>
          <input
            id="reset-confirmation"
            className="input"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            autoComplete="off"
            required
            pattern="RESET_DEMO_DATA"
            title="Enter RESET_DEMO_DATA exactly."
            disabled={pending}
          />
          {error !== null && <ErrorState error={error} />}
          {result && (
            <div className="result-panel result-positive" role="status">
              <strong>Demo data reset completed.</strong>
              <ul className="metric-reasons">
                {Object.entries(result.reset_counts).map(([key, count]) => <li key={key}><span>{key}</span><strong>{count} records</strong></li>)}
              </ul>
            </div>
          )}
          {!result && <p className="feedback">No reset has been requested in this session.</p>}
          <button className="button button-danger mt-4" type="submit" disabled={pending || confirmation !== "RESET_DEMO_DATA"}>
            {pending ? "Resetting demo data…" : "Reset demo data"}
          </button>
        </form>
      </section>
    </>
  );
}
