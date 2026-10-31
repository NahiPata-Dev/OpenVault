import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Role } from "../api/types";
import { Badge, Stepper } from "../components/UI";
import { EmptyState, ErrorState, Loading } from "../components/Feedback";
import { PageHeading, StatusBadge } from "../components/PageHeading";
import { formatIST, formatWindow, istInputToISO, statusLabel } from "../lib/format";

interface Blocker {
  code: string;
  message: string;
  next_action: string;
  requirement_codes?: string[];
}

interface EligibilityItem {
  requirement: string;
  code: string | null;
  passed: boolean;
  message: string;
  next_action: string;
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
  short_summary: string;
  description: string;
  capability_tags: string[];
  location: string;
  organization_id: string;
  organization_name: string;
  city: string;
  area: string;
  building: string;
  room: string;
  status: string;
  supervision_required: boolean;
  required_training: string[];
  weekly_operating_hours: WeeklyWindow[];
  next_availability?: string | null;
  readiness: { ready: boolean; blockers: Blocker[] };
}

interface ResourceDetail extends ResourceItem {
  owner_id: string;
  organization_type: string;
  id_required: string;
  address_note: string;
  hold_review_date: string | null;
  hold_reason: string | null;
  capacity: number | null;
  quantity: number | null;
  who_can_use: string[];
  operating_hours: WeeklyWindow[];
  supervised_windows: WeeklyWindow[];
  usage_rules: string[];
  safety_notes: string[];
  accessories_included: string[];
  condition_notes: string;
  access_model: string;
  max_session_hours: number | null;
  advance_booking_window: number | null;
  cancellation_cutoff: number;
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
  eligibility_checklist: EligibilityItem[];
}

interface ResourceListResponse {
  items: ResourceItem[];
  total: number;
}

interface RequestResponse {
  request: { id: string; status: string; created_at: string };
  eligibility: { eligible: boolean; blockers: Blocker[] };
}

interface TimelineEvent {
  timestamp: string;
  event: string;
  actor: string | null;
  summary: Record<string, unknown>;
}

interface ResourceMemory {
  demo_data: boolean;
  metrics: {
    completed_hours: number;
    unresolved_incidents: number;
  };
}

interface CatalogFilters {
  query: string;
  city: string;
  area: string;
  organization: string;
  category: string;
  status: string;
  supervised: string;
  training: string;
  sort: string;
}

const categoryIcons: Record<string, string> = {
  equipment: "◈",
  "3d printing": "⌘",
  electronics: "⌁",
  space: "⌂",
  imaging: "◎",
};

function ResourcePlaceholder({ category }: { category: string }) {
  const icon = categoryIcons[category.toLowerCase()] ?? "◇";
  return (
    <div className="resource-image-placeholder" aria-label={`${category} image placeholder`} role="img">
      <span aria-hidden="true">{icon}</span>
      <small>{statusLabel(category)} resource</small>
    </div>
  );
}

export function ResourcesPage() {
  const [searchParams] = useSearchParams();
  const initialCity = searchParams.get("city") ?? "";
  const initialFilters: CatalogFilters = {
    query: "",
    city: initialCity,
    area: "",
    organization: "",
    category: "",
    status: "",
    supervised: "",
    training: "",
    sort: "name",
  };
  const [items, setItems] = useState<ResourceItem[]>([]);
  const [categoryOptions, setCategoryOptions] = useState<string[]>([]);
  const [cityOptions, setCityOptions] = useState<string[]>([]);
  const [areaOptions, setAreaOptions] = useState<string[]>([]);
  const [organizationOptions, setOrganizationOptions] = useState<
    { id: string; name: string }[]
  >([]);
  const [filters, setFilters] = useState<CatalogFilters>(initialFilters);
  const [appliedFilters, setAppliedFilters] = useState<CatalogFilters>(initialFilters);
  const [total, setTotal] = useState(0);
  const [visibleCount, setVisibleCount] = useState(9);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async (selected: CatalogFilters) => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (selected.query.trim()) params.set("query", selected.query.trim());
    if (selected.city) params.set("city", selected.city);
    if (selected.area) params.set("area", selected.area);
    if (selected.organization) params.set("organization", selected.organization);
    if (selected.category) params.set("category", selected.category);
    if (selected.status) params.set("status", selected.status);
    if (selected.supervised) params.set("supervised", selected.supervised);
    if (selected.training) params.set("training_required", selected.training);
    if (selected.sort) params.set("sort", selected.sort);
    try {
      const result = await api.get<ResourceListResponse>(`/resources?${params.toString()}`);
      setItems(result.items);
      setTotal(result.total);
      setVisibleCount(9);
      if (!selected.query && !selected.city && !selected.area && !selected.organization && !selected.category && !selected.status && !selected.supervised && !selected.training) {
        setCategoryOptions([...new Set(result.items.map((item) => item.category))].sort());
        setCityOptions([...new Set(result.items.map((item) => item.city).filter(Boolean))].sort());
        setAreaOptions([...new Set(result.items.map((item) => item.area).filter(Boolean))].sort());
        setOrganizationOptions(
          [...new Map(
            result.items.map((item) => [
              item.organization_id,
              { id: item.organization_id, name: item.organization_name },
            ]),
          ).values()].sort((first, second) => first.name.localeCompare(second.name)),
        );
      }
    } catch (loadError) {
      setError(loadError);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(appliedFilters); }, [appliedFilters, load]);
  useEffect(() => {
    if (!initialCity) return;
    let active = true;
    void api.get<ResourceListResponse>("/resources").then(
      (result) => {
        if (!active) return;
        setCategoryOptions([...new Set(result.items.map((item) => item.category))].sort());
        setCityOptions([...new Set(result.items.map((item) => item.city).filter(Boolean))].sort());
        setAreaOptions([...new Set(result.items.map((item) => item.area).filter(Boolean))].sort());
        setOrganizationOptions(
          [...new Map(
            result.items.map((item) => [
              item.organization_id,
              { id: item.organization_id, name: item.organization_name },
            ]),
          ).values()].sort((first, second) => first.name.localeCompare(second.name)),
        );
      },
      (loadError: unknown) => active && setError(loadError),
    );
    return () => {
      active = false;
    };
  }, [initialCity]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAppliedFilters(filters);
  }

  return (
    <>
      <PageHeading
        title="Find a resource"
        description="Explore equipment and spaces shared by participating institutions. Eligibility and availability are checked by the service."
      />
      <p className="sample-data-banner" role="note">
        All institutions, people and bookings in this prototype are fictional sample data.
      </p>
      <form className="filter-bar catalog-filters" onSubmit={applyFilters}>
        <div className="filter-search">
          <label className="field-label" htmlFor="resource-search">Search resources</label>
          <input
            id="resource-search"
            className="input"
            type="search"
            value={filters.query}
            onChange={(event) => setFilters({ ...filters, query: event.target.value })}
            placeholder="Name, category, location, or capability"
          />
        </div>
        <div>
          <label className="field-label" htmlFor="resource-city">City</label>
          <select id="resource-city" className="select" value={filters.city} onChange={(event) => setFilters({ ...filters, city: event.target.value })}>
            <option value="">All cities</option>
            {cityOptions.map((entry) => <option key={entry} value={entry}>{entry}</option>)}
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor="resource-area">Area</label>
          <select id="resource-area" className="select" value={filters.area} onChange={(event) => setFilters({ ...filters, area: event.target.value })}>
            <option value="">All areas</option>
            {areaOptions.map((entry) => <option key={entry} value={entry}>{entry}</option>)}
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor="resource-organization">Organization</label>
          <select id="resource-organization" className="select" value={filters.organization} onChange={(event) => setFilters({ ...filters, organization: event.target.value })}>
            <option value="">All organizations</option>
            {organizationOptions.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor="resource-category">Category</label>
          <select id="resource-category" className="select" value={filters.category} onChange={(event) => setFilters({ ...filters, category: event.target.value })}>
            <option value="">All categories</option>
            {categoryOptions.map((entry) => <option key={entry} value={entry}>{statusLabel(entry)}</option>)}
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor="resource-status">Status</label>
          <select id="resource-status" className="select" value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="maintenance_hold">Maintenance hold</option>
            <option value="retired">Retired</option>
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor="resource-supervised">Supervision</label>
          <select id="resource-supervised" className="select" value={filters.supervised} onChange={(event) => setFilters({ ...filters, supervised: event.target.value })}>
            <option value="">Any</option>
            <option value="true">Required</option>
            <option value="false">Not required</option>
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor="resource-training">Training</label>
          <select id="resource-training" className="select" value={filters.training} onChange={(event) => setFilters({ ...filters, training: event.target.value })}>
            <option value="">Any</option>
            <option value="true">Required</option>
            <option value="false">Not required</option>
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor="resource-sort">Sort by</label>
          <select id="resource-sort" className="select" value={filters.sort} onChange={(event) => setFilters({ ...filters, sort: event.target.value })}>
            <option value="name">Name</option>
            <option value="next_availability">Next availability</option>
          </select>
        </div>
        <button className="button button-primary filter-button" type="submit" disabled={loading}>Apply filters</button>
      </form>

      {loading && <Loading label="Loading resources…" />}
      {error !== null && <ErrorState error={error} />}
      {!loading && error === null && (
        <p className="muted result-count" role="status">
          {total} {total === 1 ? "resource" : "resources"} found
        </p>
      )}
      {!loading && error === null && items.length === 0 && <EmptyState>No resources match these filters.</EmptyState>}
      {!loading && error === null && items.length > 0 && (
        <>
          <div className="resource-grid">
            {items.slice(0, visibleCount).map((resource) => (
              <article className="resource-card resource-card-detailed" key={resource.id}>
                <ResourcePlaceholder category={resource.category} />
                <div className="card-title-row">
                  <div><p className="eyebrow">{statusLabel(resource.category)}</p><h2>{resource.name}</h2></div>
                  <StatusBadge value="" ready={resource.readiness.ready} />
                </div>
                <Badge>{statusLabel(resource.status)}</Badge>
                {resource.short_summary.toLowerCase().startsWith("sample data") && <Badge>Sample data</Badge>}
                <p className="resource-summary">{resource.short_summary}</p>
                <p className="resource-institution">{resource.organization_name}</p>
                <p className="muted resource-location">
                  {[resource.area, resource.city].filter(Boolean).join(", ") || resource.location}
                </p>
                <div className="tag-list">
                  <Badge tone={resource.supervision_required ? "warning" : "neutral"}>
                    {resource.supervision_required ? "Supervision required" : "No supervision required"}
                  </Badge>
                  {resource.required_training.map((training) => <Badge tone="info" key={training}>{training}</Badge>)}
                </div>
                <Link className="button button-secondary resource-card-action" to={`/resources/${resource.id}`}>View details and request</Link>
              </article>
            ))}
          </div>
          {visibleCount < items.length && (
            <div className="load-more-row"><button className="button button-secondary" type="button" onClick={() => setVisibleCount((count) => count + 9)}>Load more resources</button></div>
          )}
        </>
      )}
    </>
  );
}

type DetailTab = "overview" | "rules" | "requirements" | "availability" | "history";

const detailTabs: { id: DetailTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "rules", label: "Rules and safety" },
  { id: "requirements", label: "Requirements" },
  { id: "availability", label: "Availability" },
  { id: "history", label: "History" },
];

const requestSteps = [
  { title: "Choose time", description: "Select a start and end time in IST." },
  { title: "Purpose", description: "Choose one use permitted by the owner." },
  { title: "Review", description: "Check eligibility and agree to the conditions." },
  { title: "Submit", description: "Send the request for a human decision." },
];

function isoToISTInput(value: string | null): string {
  if (!value) return "";
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return "";
  return new Date(timestamp + 330 * 60_000).toISOString().slice(0, 16);
}

export function ResourceDetailPage({ role }: { role: Role }) {
  const { resourceId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const draftStart = searchParams.get("start");
  const draftEnd = searchParams.get("end");
  const draftPurpose = searchParams.get("purpose");
  const isAssistantDraft = searchParams.get("assistantDraft") === "1";
  const [data, setData] = useState<ResourceResponse | null>(null);
  const [nextAvailability, setNextAvailability] = useState<string | null>(null);
  const [availabilityError, setAvailabilityError] = useState<unknown>(null);
  const [memory, setMemory] = useState<ResourceMemory | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [activeTab, setActiveTab] = useState<DetailTab>("overview");
  const [step, setStep] = useState(1);
  const [purpose, setPurpose] = useState("");
  const [startAt, setStartAt] = useState("");
  const [endAt, setEndAt] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [eligibility, setEligibility] = useState<EligibilityItem[]>([]);
  const [eligibilityLoading, setEligibilityLoading] = useState(false);
  const [eligibilityError, setEligibilityError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);
  const [requestResult, setRequestResult] = useState<RequestResponse | null>(null);
  const [requestError, setRequestError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const detail = await api.get<ResourceResponse>(`/resources/${resourceId}`);
      setData(detail);
      const allowedUses = detail.active_policy?.allowed_uses ?? [];
      setPurpose(
        draftPurpose && allowedUses.includes(draftPurpose)
          ? draftPurpose
          : allowedUses[0] ?? "",
      );
      setStartAt(isoToISTInput(draftStart));
      setEndAt(isoToISTInput(draftEnd));
      setEligibility(detail.eligibility_checklist);
    } catch (loadError) {
      setError(loadError);
    } finally {
      setLoading(false);
    }
  }, [draftEnd, draftPurpose, draftStart, resourceId]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (isAssistantDraft && !loading) {
      document.getElementById("request-title")?.scrollIntoView();
    }
  }, [isAssistantDraft, loading]);

  useEffect(() => {
    let active = true;
    setNextAvailability(null);
    setAvailabilityError(null);
    void api.get<ResourceListResponse>("/resources?sort=next_availability").then(
      (catalog) => active && setNextAvailability(catalog.items.find((item) => item.id === resourceId)?.next_availability ?? null),
      (loadError: unknown) => active && setAvailabilityError(loadError),
    );
    return () => { active = false; };
  }, [resourceId]);

  useEffect(() => {
    if (activeTab !== "history" || memory !== null || historyLoading) return;
    let active = true;
    setHistoryLoading(true);
    setHistoryError(null);
    void Promise.all([
      api.get<ResourceMemory>(`/resources/${resourceId}/memory`),
      api.get<{ items: TimelineEvent[] }>(`/resources/${resourceId}/timeline`),
    ]).then(([memoryResult, timelineResult]) => {
      if (!active) return;
      setMemory(memoryResult);
      setTimeline(timelineResult.items);
    }).catch((loadError: unknown) => active && setHistoryError(loadError))
      .finally(() => active && setHistoryLoading(false));
    return () => { active = false; };
  }, [activeTab, memory, resourceId]);

  async function checkEligibility() {
    setEligibilityLoading(true);
    setEligibilityError(null);
    try {
      const params = new URLSearchParams({
        start_at: istInputToISO(startAt),
        end_at: istInputToISO(endAt),
        purpose,
      });
      const result = await api.get<ResourceResponse>(`/resources/${resourceId}?${params.toString()}`);
      setEligibility(result.eligibility_checklist);
      setStep(3);
    } catch (checkError) {
      setEligibilityError(checkError);
    } finally {
      setEligibilityLoading(false);
    }
  }

  async function submitRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!agreed) return;
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

  function continueToPurpose() {
    if (new Date(istInputToISO(endAt)) <= new Date(istInputToISO(startAt))) {
      setEligibilityError(new Error("End time must be after start time."));
      return;
    }
    setEligibilityError(null);
    setStep(2);
  }

  if (loading) return <Loading label="Loading resource details…" />;
  if (error !== null) return <ErrorState error={error} />;
  if (!data) return <EmptyState>Resource details are unavailable.</EmptyState>;

  const { resource, active_policy: policy } = data;
  const requirements = policy?.structured_requirements;
  const completedSessions = timeline.filter((event) => ["booking.closed", "booking.closed_after_review"].includes(event.event)).length;
  const incidentCount = timeline.filter((event) => event.event === "incident.opened").length;

  return (
    <>
      <Link className="back-link" to="/resources">← Back to resources</Link>
      <PageHeading
        eyebrow={statusLabel(resource.category)}
        title={resource.name}
        description={`${resource.location} · ${statusLabel(resource.status)}`}
      />
      {resource.is_demo && <Badge>Sample data</Badge>}
      <div className="resource-detail-badges">
        <StatusBadge value="" ready={data.readiness.ready} />
        <Badge>{statusLabel(resource.status)}</Badge>
      </div>
      <article className="panel institution-profile">
        <div>
          <p className="eyebrow">INSTITUTION PROFILE</p>
          <h2>{resource.organization_name}</h2>
        </div>
        <dl className="institution-profile-facts">
          <div><dt>City</dt><dd>{resource.city || "Not provided by the catalog API"}</dd></div>
          <div><dt>Area</dt><dd>{resource.area || "Not provided by the catalog API"}</dd></div>
          <div><dt>Type</dt><dd>{resource.organization_type}</dd></div>
        </dl>
      </article>
      <nav className="detail-tabs" role="tablist" aria-label="Resource details">
        {detailTabs.map((tab, index) => (
          <button
            key={tab.id}
            id={`resource-tab-${tab.id}`}
            type="button"
            role="tab"
            aria-controls={`resource-panel-${tab.id}`}
            aria-selected={activeTab === tab.id}
            tabIndex={activeTab === tab.id ? 0 : -1}
            onClick={() => setActiveTab(tab.id)}
            onKeyDown={(event) => {
              if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
              event.preventDefault();
              const nextIndex = (index + (event.key === "ArrowRight" ? 1 : -1) + detailTabs.length) % detailTabs.length;
              const nextTab = detailTabs[nextIndex];
              setActiveTab(nextTab.id);
              document.getElementById(`resource-tab-${nextTab.id}`)?.focus();
            }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {activeTab === "overview" && (
        <section className="detail-layout" id="resource-panel-overview" role="tabpanel" aria-labelledby="resource-tab-overview">
          <article className="panel">
            <h2>About this resource</h2>
            <p><strong>Summary:</strong> {resource.short_summary}</p>
            <p>{resource.description || resource.short_summary}</p>
            <p><strong>Category:</strong> {statusLabel(resource.category)}</p>
            <p><strong>Resource ID:</strong> <code>{resource.id}</code></p>
            <p><strong>Resource owner ID:</strong> <code>{resource.owner_id}</code></p>
            <p><strong>Organization ID:</strong> <code>{resource.organization_id}</code></p>
            <h3>Location</h3>
            <p>{[resource.city, resource.area, resource.building, resource.room, resource.address_note].filter(Boolean).join(" · ") || resource.location}</p>
            <p><strong>Location label:</strong> {resource.location}</p>
            {resource.capacity !== null && <p><strong>Capacity:</strong> {resource.capacity}</p>}
            {resource.quantity !== null && <p><strong>Quantity:</strong> {resource.quantity}</p>}
            {resource.who_can_use.length > 0 && <><h3>Who can use it</h3><ul className="simple-list">{resource.who_can_use.map((entry) => <li key={entry}>{entry}</li>)}</ul></>}
            <h3>ID needed</h3>
            <p>{resource.id_required}</p>
          </article>
          <article className="panel">
            <h2>Operating hours (IST)</h2>
            {resource.operating_hours.length ? <ul className="simple-list">{resource.operating_hours.map((window, index) => <li key={`${window.weekday}-${index}`}>{formatWindow(window)}</li>)}</ul> : <p className="muted">No operating hours are listed by the service.</p>}
            <p className="helper">Hours describe when this resource may be requested; the owner still reviews every request.</p>
            {resource.hold_reason && <p className="alert alert-warning"><strong>Maintenance hold</strong>{resource.hold_reason}{resource.hold_review_date && ` Review date: ${resource.hold_review_date}.`}</p>}
            <h3>Booking and access</h3>
            <dl className="resource-detail-facts">
              <div><dt>Maximum session</dt><dd>{resource.max_session_hours !== null ? `${resource.max_session_hours} hours` : "Not specified"}</dd></div>
              <div><dt>Maximum duration</dt><dd>{resource.max_duration_minutes !== null ? `${resource.max_duration_minutes} minutes` : "Not specified"}</dd></div>
              <div><dt>Advance booking window</dt><dd>{resource.advance_booking_window !== null ? `${resource.advance_booking_window} days` : "Not specified"}</dd></div>
              <div><dt>Cancellation cutoff</dt><dd>{resource.cancellation_cutoff} hours before the start</dd></div>
              <div><dt>Booking model</dt><dd>{resource.exclusive_booking ? "Exclusive booking" : "Shared capacity"}</dd></div>
              <div><dt>Access model</dt><dd>{resource.access_model}</dd></div>
            </dl>
            <h3>Capability tags</h3>
            {resource.capability_tags.length > 0 ? <div className="tag-list">{resource.capability_tags.map((tag) => <Badge key={tag}>{tag}</Badge>)}</div> : <p className="muted">No capability tags are listed.</p>}
          </article>
        </section>
      )}

      {activeTab === "rules" && (
        <section className="detail-layout" id="resource-panel-rules" role="tabpanel" aria-labelledby="resource-tab-rules">
          <article className="panel">
            <h2>Use rules</h2>
            {resource.usage_rules.length ? <ul className="simple-list">{resource.usage_rules.map((rule) => <li key={rule}>{rule}</li>)}</ul> : <p className="muted">No additional use rules are listed.</p>}
            <h3>Allowed uses</h3>
            {policy?.allowed_uses.length ? <ul className="simple-list">{policy.allowed_uses.map((use) => <li key={use}>{statusLabel(use)}</li>)}</ul> : <p>No active allowed-use policy is available.</p>}
            <h3>Required training</h3>
            {resource.required_training.length ? <ul className="simple-list">{resource.required_training.map((entry) => <li key={entry}>{entry}</li>)}</ul> : <p className="muted">No required training is listed.</p>}
            <h3>Supervision windows (IST)</h3>
            {resource.supervised_windows.length > 0 ? <ul className="simple-list">{resource.supervised_windows.map((window, index) => <li key={`${window.weekday}-${index}`}>{formatWindow(window)}</li>)}</ul> : <p className="muted">No supervised windows are listed.</p>}
            <p className="helper">Your selected use is recorded with the request so the owner can review its fit.</p>
          </article>
          <article className="panel">
            <h2>Safety and condition</h2>
            {resource.safety_notes.length ? <ul className="simple-list">{resource.safety_notes.map((note) => <li key={note}>{note}</li>)}</ul> : <p className="muted">No additional safety notes are listed.</p>}
            <h3>Included accessories</h3>
            {resource.accessories_included.length ? <ul className="simple-list">{resource.accessories_included.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No accessories are listed.</p>}
            {resource.condition_notes && <p><strong>Condition notes:</strong> {resource.condition_notes}</p>}
            <h3>Access model</h3>
            <p>{resource.access_model}</p>
            <p className="helper">The check-in and return checklist records condition and accessories to support a consistent handover.</p>
          </article>
        </section>
      )}

      {activeTab === "requirements" && (
        <section className="detail-layout" id="resource-panel-requirements" role="tabpanel" aria-labelledby="resource-tab-requirements">
          <article className="panel">
            <h2>Resource requirements</h2>
            <div className="tag-list">
              <Badge tone={requirements?.supervisor_required ? "warning" : "neutral"}>{requirements?.supervisor_required ? "Supervision required" : "No supervision required"}</Badge>
              {(requirements?.training_codes ?? resource.required_training).map((code) => <Badge tone="info" key={code}>{code}</Badge>)}
            </div>
            {resource.supervised_windows.length > 0 && <ul className="simple-list mt-4">{resource.supervised_windows.map((window, index) => <li key={`${window.weekday}-${index}`}>{formatWindow(window)}</li>)}</ul>}
            {resource.supervised_windows.length === 0 && <p className="muted">No supervised windows are listed.</p>}
            <p className="helper">Eligibility is evaluated for the time you request. Training and supervision rules are taken from the active policy.</p>
          </article>
          <article className="panel">
            <h2>Your eligibility</h2>
            {eligibility.length > 0 ? (
              <ul className="eligibility-list">
                {eligibility.map((item, index) => (
                  <li className={item.passed ? "eligibility-pass" : "eligibility-fail"} key={`${item.code ?? item.requirement}-${index}`}>
                    <span className="eligibility-icon" aria-hidden="true">{item.passed ? "✓" : "!"}</span>
                    <div><strong>{item.requirement}</strong><p>{item.message}</p>{!item.passed && <p><strong>Next action:</strong> {item.next_action}</p>}</div>
                    <span className="sr-only">{item.passed ? "Pass" : "Fail"}</span>
                  </li>
                ))}
              </ul>
            ) : <p>Choose a time in the request form to check your eligibility for that window.</p>}
            <p className="helper">Eligibility checks support safe access; a manager still makes the allocation decision.</p>
          </article>
        </section>
      )}

      {activeTab === "availability" && (
        <section className="detail-layout" id="resource-panel-availability" role="tabpanel" aria-labelledby="resource-tab-availability">
          <article className="panel">
            <h2>Weekly availability</h2>
            {resource.operating_hours.length ? <ul className="simple-list">{resource.operating_hours.map((window, index) => <li key={`${window.weekday}-${index}`}>{formatWindow(window)}</li>)}</ul> : <p>No weekly availability was returned.</p>}
            {availabilityError !== null ? <ErrorState error={availabilityError} /> : <p><strong>Next available time returned:</strong> {nextAvailability ? formatIST(nextAvailability) : "Not currently provided"}</p>}
            <p className="helper">The requester API does not expose other users’ booked slots. This schedule and next-time estimate come from the resource service; final eligibility is rechecked when you submit.</p>
          </article>
          <article className="panel">
            <h2>Booking conditions</h2>
            <p><strong>Maximum session:</strong> {resource.max_session_hours ? `${resource.max_session_hours} hours` : resource.max_duration_minutes ? `${resource.max_duration_minutes} minutes` : "Not specified"}</p>
            <p><strong>Advance booking:</strong> {resource.advance_booking_window === null ? "Not specified" : `${resource.advance_booking_window} days`}</p>
            <p><strong>Cancellation cutoff:</strong> {resource.cancellation_cutoff} hours before the session</p>
            <p className="helper">These conditions help determine whether a requested time can be accepted by the service.</p>
          </article>
        </section>
      )}

      {activeTab === "history" && (
        <section className="panel" id="resource-panel-history" role="tabpanel" aria-labelledby="resource-tab-history">
          <h2>Resource history</h2>
          {historyLoading && <Loading label="Loading resource history…" />}
          {historyError !== null && <ErrorState error={historyError} />}
          {memory && (
            <div className="history-summary">
            <article><span>Completed sessions recorded</span><strong>{completedSessions}</strong>{memory.demo_data && <small>DEMO DATA — not live institutional statistics</small>}</article>
            <article><span>Unresolved incidents</span><strong>{memory.metrics.unresolved_incidents}</strong>{memory.demo_data && <small>DEMO DATA — not live institutional statistics</small>}</article>
            <article><span>Incident reports opened</span><strong>{incidentCount}</strong>{memory.demo_data && <small>DEMO DATA — not live institutional statistics</small>}</article>
            </div>
          )}
          {memory && <p className="helper">Counts come from the resource audit timeline and Resource Memory API. Only unresolved incidents are counted as current open incidents.</p>}
          {!historyLoading && !historyError && timeline.length === 0 && memory && <EmptyState>No completed sessions or incident events were returned for this resource.</EmptyState>}
        </section>
      )}

      {role === "requester" && (
        <section className="panel request-panel" aria-labelledby="request-title">
          <h2 id="request-title">Request this resource</h2>
          <p className="helper">A submitted request is not an approval or booking. Times are entered in India Standard Time (IST).</p>
          <Stepper steps={requestSteps} activeStep={step} />
          {requestResult ? (
            <div className={`result-panel ${requestResult.eligibility.eligible ? "result-positive" : "result-negative"}`} role="status" aria-live="polite">
              {requestResult.eligibility.eligible ? (
                <>
                  <h3>Submitted — pending review</h3>
                  <p>Your request is saved as {statusLabel(requestResult.request.status)}. The resource owner or manager will review it; no booking is confirmed yet.</p>
                  <Link className="button button-secondary" to="/requests">View my requests</Link>
                </>
              ) : (
                <>
                  <h3>INELIGIBLE</h3>
                  <p>The request was saved, but the service found these blockers:</p>
                  <ul className="blocker-list">{requestResult.eligibility.blockers.map((blocker, index) => <li className="blocker-item" key={`${blocker.code}-${index}`}><strong>{statusLabel(blocker.code)}</strong><p>{blocker.message}</p><p><strong>Next action:</strong> {blocker.next_action}</p></li>)}</ul>
                  <Link className="button button-secondary" to="/requests">View my requests</Link>
                </>
              )}
            </div>
          ) : (
            <form onSubmit={(event) => void submitRequest(event)}>
              {step === 1 && (
                <section className="request-step">
                  <h3>1. Choose time</h3>
                  <div className="form-grid">
                    <div><label className="field-label" htmlFor="request-start">Start (IST)</label><input id="request-start" className="input" type="datetime-local" required value={startAt} onChange={(event) => setStartAt(event.target.value)} /></div>
                    <div><label className="field-label" htmlFor="request-end">End (IST)</label><input id="request-end" className="input" type="datetime-local" required value={endAt} onChange={(event) => setEndAt(event.target.value)} /></div>
                  </div>
                  <p className="helper">Your requested window is stored with the request and checked against operating hours, holds, training, supervision, and bookings.</p>
                  <button className="button button-primary" type="button" disabled={!startAt || !endAt} onClick={(event) => {
                    const form = event.currentTarget.form;
                    if (form?.reportValidity()) {
                      try { continueToPurpose(); } catch { setEligibilityError(new Error("Enter valid start and end times.")); }
                    }
                  }}>Continue</button>
                </section>
              )}
              {step === 2 && (
                <section className="request-step">
                  <h3>2. Purpose and allowed use</h3>
                  <label className="field-label" htmlFor="request-purpose">How will you use this resource?</label>
                  <select id="request-purpose" className="select" required value={purpose} onChange={(event) => setPurpose(event.target.value)}>
                    <option value="" disabled>Select a permitted use</option>
                    {(policy?.allowed_uses ?? []).map((use) => <option value={use} key={use}>{statusLabel(use)}</option>)}
                  </select>
                  <p className="helper">Your purpose is recorded with the request so the resource owner can verify it matches the policy.</p>
                  <div className="card-actions"><button className="button button-secondary" type="button" onClick={() => setStep(1)}>Back</button><button className="button button-primary" type="button" disabled={!purpose || eligibilityLoading} onClick={() => void checkEligibility()}>{eligibilityLoading ? "Checking…" : "Review requirements"}</button></div>
                </section>
              )}
              {step === 3 && (
                <section className="request-step">
                  <h3>3. Review requirements and agree</h3>
                  <p><strong>Requested window:</strong> {formatIST(istInputToISO(startAt))} – {formatIST(istInputToISO(endAt))}</p>
                  <p><strong>Allowed use:</strong> {statusLabel(purpose)}</p>
                  {eligibility.length ? <ul className="eligibility-list">{eligibility.map((item, index) => <li className={item.passed ? "eligibility-pass" : "eligibility-fail"} key={`${item.code ?? item.requirement}-${index}`}><span className="eligibility-icon" aria-hidden="true">{item.passed ? "✓" : "!"}</span><div><strong>{item.requirement}</strong><p>{item.message}</p>{!item.passed && <p><strong>Next action:</strong> {item.next_action}</p>}</div></li>)}</ul> : <p>The service did not return a separate eligibility checklist. Submission will be evaluated by the backend.</p>}
                  <p className="helper">These checks are a point-in-time assessment. The backend checks eligibility again when you submit. Your agreement is part of this form; the request API does not expose a separate saved agreement field.</p>
                  <label className="agreement-check"><input type="checkbox" checked={agreed} onChange={(event) => setAgreed(event.target.checked)} /><span>I have reviewed the resource rules and safety notes and agree to follow them during any approved session.</span></label>
                  <div className="card-actions"><button className="button button-secondary" type="button" onClick={() => setStep(2)}>Back</button><button className="button button-primary" type="button" disabled={!agreed} onClick={() => setStep(4)}>Continue to submit</button></div>
                </section>
              )}
              {step === 4 && (
                <section className="request-step">
                  <h3>4. Submit request</h3>
                  <dl className="request-details"><div><dt>Resource</dt><dd>{resource.name}</dd></div><div><dt>Requested window</dt><dd>{formatIST(istInputToISO(startAt))} – {formatIST(istInputToISO(endAt))}</dd></div><div><dt>Purpose</dt><dd>{statusLabel(purpose)}</dd></div><div><dt>Requirements reviewed</dt><dd>{agreed ? "Agreed" : "Not agreed"}</dd></div></dl>
                  <p className="helper">The request and your agreement are submitted to the service. A resource owner or manager makes the decision.</p>
                  {eligibilityError !== null && <ErrorState error={eligibilityError} />}
                  {requestError !== null && <ErrorState error={requestError} />}
                  <div className="card-actions"><button className="button button-secondary" type="button" onClick={() => setStep(3)}>Back</button><button className="button button-primary" type="submit" disabled={submitting || !agreed}>{submitting ? "Submitting…" : "Submit request"}</button></div>
                </section>
              )}
              {step < 4 && eligibilityError !== null && <ErrorState error={eligibilityError} />}
            </form>
          )}
        </section>
      )}
    </>
  );
}
