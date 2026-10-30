import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Role } from "../api/types";
import { ErrorState, EmptyState, Loading } from "../components/Feedback";
import { PageHeading, StatusBadge } from "../components/PageHeading";
import { formatWindow, istInputToISO, statusLabel } from "../lib/format";

interface Blocker {
  code: string;
  message: string;
  next_action: string;
  requirement_codes?: string[];
}

interface WeeklyWindow {
  weekday: number;
  start: string;
  end: string;
}

interface ResourceItem {
  id: string;
  name: string;
  category: string;
  capability_tags: string[];
  location: string;
  status: string;
  weekly_operating_hours: WeeklyWindow[];
  readiness: { ready: boolean; blockers: Blocker[] };
}

interface ResourceDetail extends ResourceItem {
  owner_id: string;
  hold_review_date: string | null;
  max_duration_minutes: number | null;
  exclusive_booking: boolean;
  is_demo: boolean;
}

interface Policy {
  structured_requirements: {
    training_codes: string[];
    supervisor_required: boolean;
    supervised_windows: WeeklyWindow[];
  };
  allowed_uses: string[];
  priority_policy: Record<string, unknown>;
}

interface ResourceResponse {
  resource: ResourceDetail;
  active_policy: Policy | null;
  readiness: { ready: boolean; blockers: Blocker[] };
}

interface ResourceListResponse {
  items: ResourceItem[];
  total: number;
}

interface RequestResponse {
  request: { id: string; status: string; created_at: string };
  eligibility: { eligible: boolean; blockers: Blocker[] };
}

export function ResourcesPage() {
  const [items, setItems] = useState<ResourceItem[]>([]);
  const [categoryOptions, setCategoryOptions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");

  const load = useCallback(async (filters = { query: "", category: "" }) => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (filters.query.trim()) params.set("query", filters.query.trim());
    if (filters.category) params.set("category", filters.category);
    try {
      const result = await api.get<ResourceListResponse>(`/resources?${params.toString()}`);
      setItems(result.items);
      if (!filters.query && !filters.category) {
        setCategoryOptions([...new Set(result.items.map((item) => item.category))].sort());
      }
    } catch (loadError) {
      setError(loadError);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function applyFilters(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const filters = { query, category };
    void load(filters);
  }

  return (
    <>
      <PageHeading
        title="Find a resource"
        description="Browse lab equipment and spaces. Readiness is evaluated by the backend."
      />
      <form className="filter-bar" onSubmit={applyFilters}>
        <div className="filter-search">
          <label className="field-label" htmlFor="resource-search">Search resources</label>
          <input
            id="resource-search"
            className="input"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Name, category, location, or capability"
          />
        </div>
        <div>
          <label className="field-label" htmlFor="resource-category">Category</label>
          <select
            id="resource-category"
            className="select"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="">All categories</option>
            {categoryOptions.map((entry) => <option key={entry} value={entry}>{statusLabel(entry)}</option>)}
          </select>
        </div>
        <button className="button button-primary filter-button" type="submit" disabled={loading}>
          Search
        </button>
      </form>

      {loading ? <Loading label="Loading resources…" /> : null}
      {error !== null && <ErrorState error={error} />}
      {!loading && error === null && items.length === 0 && (
        <EmptyState>No resources match these filters.</EmptyState>
      )}
      {!loading && error === null && items.length > 0 && (
        <>
          <p className="muted result-count">{items.length} {items.length === 1 ? "resource" : "resources"}</p>
          <div className="resource-grid">
            {items.map((resource) => (
              <article className="resource-card" key={resource.id}>
                <div className="card-title-row">
                  <div>
                    <p className="eyebrow">{statusLabel(resource.category)}</p>
                    <h2>{resource.name}</h2>
                  </div>
                  <StatusBadge value={resource.status} ready={resource.readiness.ready} />
                </div>
                <p className="muted">{resource.location}</p>
                <p className="tag-list">
                  {resource.capability_tags.map((tag) => <span className="tag" key={tag}>{tag}</span>)}
                </p>
                <Link className="button button-secondary" to={`/resources/${resource.id}`}>View details</Link>
              </article>
            ))}
          </div>
        </>
      )}
    </>
  );
}

export function ResourceDetailPage({ role }: { role: Role }) {
  const { resourceId = "" } = useParams();
  const [data, setData] = useState<ResourceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [purpose, setPurpose] = useState("");
  const [startAt, setStartAt] = useState("");
  const [endAt, setEndAt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [requestResult, setRequestResult] = useState<RequestResponse | null>(null);
  const [requestError, setRequestError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<ResourceResponse>(`/resources/${resourceId}`);
      setData(result);
      setPurpose(result.active_policy?.allowed_uses[0] ?? "");
    } catch (loadError) {
      setError(loadError);
    } finally {
      setLoading(false);
    }
  }, [resourceId]);

  useEffect(() => { void load(); }, [load]);

  async function submitRequest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setRequestError(null);
    setRequestResult(null);
    try {
      const result = await api.post<RequestResponse>("/requests", {
        resource_id: resourceId,
        purpose,
        start_at: istInputToISO(startAt),
        end_at: istInputToISO(endAt),
      });
      setRequestResult(result);
    } catch (submitError) {
      setRequestError(submitError);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <Loading label="Loading resource details…" />;
  if (error !== null) return <ErrorState error={error} />;
  if (!data) return <EmptyState>Resource details are unavailable.</EmptyState>;

  const { resource, active_policy: policy, readiness } = data;
  const windows = resource.weekly_operating_hours;
  const requirements = policy?.structured_requirements;

  return (
    <>
      <Link className="back-link" to="/resources">← Back to resources</Link>
      <PageHeading
        eyebrow={statusLabel(resource.category)}
        title={resource.name}
        description={`${resource.location} · ${statusLabel(resource.status)}`}
      />
      <Link className="button button-secondary resource-memory-link" to={`/resources/${resourceId}/memory`}>View Resource Memory</Link>
      <div className="detail-layout">
        <section className="panel" aria-labelledby="readiness-title">
          <div className="panel-heading">
            <h2 id="readiness-title">Readiness</h2>
            <StatusBadge value={resource.status} ready={readiness.ready} />
          </div>
          {readiness.blockers.length === 0 ? (
            <p className="success-text">No current blockers reported by the backend.</p>
          ) : (
            <ul className="blocker-list">
              {readiness.blockers.map((blocker, index) => (
                <li className="blocker-item" key={`${blocker.code}-${index}`}>
                  <strong>{blocker.code}</strong>
                  <p>{blocker.message}</p>
                  <p><span className="font-semibold">Next action:</span> {blocker.next_action}</p>
                  {blocker.requirement_codes && <p>Requirements: {blocker.requirement_codes.join(", ")}</p>}
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="panel" aria-labelledby="requirements-title">
          <h2 id="requirements-title">Requirements and schedule</h2>
          <h3>Required training</h3>
          {requirements?.training_codes.length ? (
            <ul className="simple-list">{requirements.training_codes.map((code) => <li key={code}>{code}</li>)}</ul>
          ) : <p className="muted">No training codes listed in the active policy.</p>}
          <h3>Operating hours (IST)</h3>
          {windows.length ? (
            <ul className="simple-list">{windows.map((window, index) => <li key={`${window.weekday}-${index}`}>{formatWindow(window)}</li>)}</ul>
          ) : <p className="muted">No operating hours returned.</p>}
          <h3>Supervision</h3>
          {!requirements?.supervisor_required ? (
            <p className="muted">Supervision is not required by the active policy.</p>
          ) : (
            <>
              <p>Supervision is required for this resource.</p>
              {requirements.supervised_windows.length ? (
                <ul className="simple-list">{requirements.supervised_windows.map((window, index) => <li key={`${window.weekday}-${index}`}>{formatWindow(window)}</li>)}</ul>
              ) : <p className="muted">No supervised windows are listed.</p>}
            </>
          )}
          <h3>Allowed uses</h3>
          {policy?.allowed_uses.length ? <p>{policy.allowed_uses.map(statusLabel).join(", ")}</p> : <p className="muted">No active policy is available.</p>}
          {resource.max_duration_minutes !== null && <p className="mt-3"><strong>Maximum session:</strong> {resource.max_duration_minutes} minutes</p>}
          <p><strong>Booking model:</strong> {resource.exclusive_booking ? "Exclusive booking" : "Shared booking"}</p>
          {resource.hold_review_date && <p className="mt-4"><strong>Hold review date:</strong> {resource.hold_review_date}</p>}
        </section>
      </div>

      {role === "requester" && (
        <section className="panel request-panel" aria-labelledby="request-title">
          <h2 id="request-title">Request this resource</h2>
          <p className="helper">Times are entered in India Standard Time (IST). Your request is evaluated by the backend; submitting does not approve or reserve a booking.</p>
          <form onSubmit={(event) => void submitRequest(event)}>
            <div className="form-grid">
              <div>
                <label className="field-label" htmlFor="request-purpose">Purpose / allowed use</label>
                <select
                  id="request-purpose"
                  className="select"
                  required
                  value={purpose}
                  onChange={(event) => setPurpose(event.target.value)}
                  disabled={!policy || submitting}
                >
                  <option value="" disabled>Select a permitted use</option>
                  {(policy?.allowed_uses ?? []).map((use) => <option value={use} key={use}>{statusLabel(use)}</option>)}
                </select>
                <p className="helper">The backend accepts the allowed-use value as the request purpose.</p>
              </div>
              <div>
                <label className="field-label" htmlFor="request-start">Start (IST)</label>
                <input id="request-start" className="input" type="datetime-local" required value={startAt} onChange={(event) => setStartAt(event.target.value)} disabled={submitting} />
              </div>
              <div>
                <label className="field-label" htmlFor="request-end">End (IST)</label>
                <input id="request-end" className="input" type="datetime-local" required value={endAt} onChange={(event) => setEndAt(event.target.value)} disabled={submitting} />
              </div>
            </div>
            {requestError !== null && <ErrorState error={requestError} />}
            {requestResult && (
              <div className={`result-panel ${requestResult.eligibility.eligible ? "result-positive" : "result-negative"}`} role="status" aria-live="polite">
                <h3>{requestResult.eligibility.eligible ? "PENDING REVIEW" : "INELIGIBLE"}</h3>
                {requestResult.eligibility.eligible ? (
                  <p>Your request is awaiting a manager decision. No booking has been created.</p>
                ) : (
                  <>
                    <p>The backend saved the request as ineligible. Review each blocker:</p>
                    <ul className="list-disc pl-5">
                      {requestResult.eligibility.blockers.map((blocker, index) => <li key={`${blocker.code}-${index}`}><strong>{blocker.code}:</strong> {blocker.message}{blocker.next_action ? ` Next action: ${blocker.next_action}` : ""}</li>)}
                    </ul>
                  </>
                )}
              </div>
            )}
            <button className="button button-primary mt-4" type="submit" disabled={submitting || !policy || !purpose}>
              {submitting ? "Sending request…" : "Submit request"}
            </button>
          </form>
        </section>
      )}
    </>
  );
}
