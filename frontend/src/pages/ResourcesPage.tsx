import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Box, Building2, Camera, Cpu, FlaskConical, Printer, Wrench } from "lucide-react";
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

const categoryIcons = {
  equipment: Box,
  "3d printing": Printer,
  electronics: Cpu,
  space: Building2,
  imaging: Camera,
  laboratory: FlaskConical,
};

function ResourcePlaceholder({ category }: { category: string }) {
  const Icon = categoryIcons[category.toLowerCase() as keyof typeof categoryIcons] ?? Wrench;
  return (
    <div className="resource-image-placeholder" aria-label={`${category} image placeholder`} role="img">
      <Icon size={34} strokeWidth={1.7} aria-hidden="true" />
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
      {!loading && error === null && items.length === 0 && (
        <EmptyState
          title="No resources match these filters"
          action={<button className="button button-secondary" type="button" onClick={() => {
            setFilters({ ...initialFilters, city: "" });
            setAppliedFilters({ ...initialFilters, city: "" });
          }}>Clear filters</button>}
        >
          Try a broader search or clear the selected filters.
        </EmptyState>
      )}
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
                <StatusBadge value={resource.status} />
                {resource.short_summary.toLowerCase().startsWith("sample data") && <Badge>Sample data</Badge>}
                <p className="resource-summary">{resource.short_summary}</p>
                <p className="resource-institution">{resource.organization_name}</p>
                <p className="muted resource-location">
                  {[resource.area, resource.city].filter(Boolean).join(", ") || resource.location}
                </p>
                <div className="resource-bookability" aria-label={`Can I book this? ${resource.status === "active" && resource.readiness.ready ? "Time-specific checks still apply" : "Review requirements before requesting"}`}>
                  <strong>Can I book this?</strong>
                  <span>{resource.status === "active" && resource.readiness.ready
                    ? "Ready to request; time-specific checks still apply."
                    : "Review the requirements and blockers before requesting."}</span>
                </div>
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

const requestSteps = [
  { title: "Choose a time", description: "Pick the session time in IST." },
  { title: "Purpose and checks", description: "Choose a use and review requirements." },
  { title: "Review and send", description: "Check your summary and submit for review." },
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
  const [historyExpanded, setHistoryExpanded] = useState(false);
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
    if (!historyExpanded || memory !== null) return;
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
      .finally(() => setHistoryLoading(false));
    return () => { active = false; };
  }, [historyExpanded, memory, resourceId]);

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
  const operatingHours = resource.operating_hours.length
    ? resource.operating_hours
    : resource.weekly_operating_hours;
  const supervisionRequired = requirements?.supervisor_required ?? resource.supervision_required;
  const requestReadiness = resource.status !== "active"
    ? "Not accepting new requests"
    : data.readiness.ready ? "No current access blockers" : "Some requirements need attention";
  const completedSessions = timeline.filter((event) => ["booking.closed", "booking.closed_after_review"].includes(event.event)).length;
  const incidentCount = timeline.filter((event) => event.event === "incident.opened").length;

  return (
    <>
      <Link className="back-link" to="/resources">← Back to resources</Link>
      <section className="resource-summary-card" aria-labelledby="resource-summary-title">
        <div className="resource-summary-heading">
          <div>
            <p className="eyebrow">{statusLabel(resource.category)}</p>
            <h1 id="resource-summary-title">{resource.name}</h1>
            <p>{resource.organization_name} · {[resource.area, resource.city].filter(Boolean).join(", ") || resource.location}</p>
          </div>
          <div className="resource-summary-badges">
            {resource.is_demo && <Badge>Sample data</Badge>}
            <StatusBadge value={resource.status} />
          </div>
        </div>
        <div className="resource-summary-bottom">
          <div>
            <strong>{role === "requester"
              ? requestReadiness
              : statusLabel(resource.status)}</strong>
            <p>{role === "requester"
              ? "Time-specific eligibility is checked when you request. A manager reviews every request."
              : `${resource.organization_type} · ${resource.city}, ${resource.area}`}</p>
          </div>
          <a
            className="button button-primary"
            href={role === "requester" ? "#request-title" : "#resource-requirements"}
            onClick={() => {
              if (role !== "requester") {
                document.getElementById("resource-requirements")?.setAttribute("open", "");
              }
            }}
          >
            {role === "requester" ? "Start a request" : "Check requirements"}
          </a>
        </div>
      </section>

      <div className="resource-disclosures">
        <details className="resource-disclosure" open>
          <summary><span>About and location</span><small>Institution, place, and who can use it</small></summary>
          <div className="resource-disclosure-content">
            <article className="panel institution-profile">
              <div><p className="eyebrow">INSTITUTION PROFILE</p><h2>{resource.organization_name}</h2></div>
              <dl className="institution-profile-facts">
                <div><dt>City</dt><dd>{resource.city || "Not provided by the catalog API"}</dd></div>
                <div><dt>Area</dt><dd>{resource.area || "Not provided by the catalog API"}</dd></div>
                <div><dt>Type</dt><dd>{resource.organization_type}</dd></div>
              </dl>
            </article>
            <div className="detail-layout">
              <article className="panel">
                <h2>About this resource</h2>
                <p><strong>Summary:</strong> {resource.short_summary}</p>
                <p>{resource.description || resource.short_summary}</p>
                <p><strong>Category:</strong> {statusLabel(resource.category)}</p>
                <h3>Location</h3>
                <p>{[resource.city, resource.area, resource.building, resource.room, resource.address_note].filter(Boolean).join(" · ") || resource.location}</p>
                <p><strong>Location label:</strong> {resource.location}</p>
                {resource.capacity !== null && <p><strong>Capacity:</strong> {resource.capacity}</p>}
                {resource.quantity !== null && <p><strong>Quantity:</strong> {resource.quantity}</p>}
                <h3>Who can use it</h3>
                {resource.who_can_use.length > 0 ? <ul className="simple-list">{resource.who_can_use.map((entry) => <li key={entry}>{entry}</li>)}</ul> : <p className="muted">No user groups are listed.</p>}
                <h3>ID needed</h3><p>{resource.id_required}</p>
              </article>
              <article className="panel">
                <h2>Resource profile</h2>
                <p><strong>Resource ID:</strong> <code>{resource.id}</code></p>
                <p><strong>Resource owner ID:</strong> <code>{resource.owner_id}</code></p>
                <p><strong>Organization ID:</strong> <code>{resource.organization_id}</code></p>
                <h3>Capabilities</h3>
                {resource.capability_tags.length > 0
                  ? <div className="tag-list">{resource.capability_tags.map((tag) => <Badge key={tag}>{tag}</Badge>)}</div>
                  : <p className="muted">No capability tags are listed.</p>}
              </article>
            </div>
          </div>
        </details>

        <details className="resource-disclosure">
          <summary><span>Rules and safety</span><small>Allowed use, precautions, and included accessories</small></summary>
          <div className="resource-disclosure-content detail-layout">
            <article className="panel">
              <h2>Use rules</h2>
              {resource.usage_rules.length ? <ul className="simple-list">{resource.usage_rules.map((rule) => <li key={rule}>{rule}</li>)}</ul> : <p className="muted">No additional use rules are listed.</p>}
              <h3>Allowed uses</h3>
              {policy?.allowed_uses.length ? <ul className="simple-list">{policy.allowed_uses.map((use) => <li key={use}>{statusLabel(use)}</li>)}</ul> : <p>No active allowed-use policy is available.</p>}
              <h3>Access Contract (session conditions)</h3><p>{resource.access_model}</p>
            </article>
            <article className="panel">
              <h2>Safety and condition</h2>
              {resource.safety_notes.length ? <ul className="simple-list">{resource.safety_notes.map((note) => <li key={note}>{note}</li>)}</ul> : <p className="muted">No additional safety notes are listed.</p>}
              <h3>Included accessories</h3>
              {resource.accessories_included.length ? <ul className="simple-list">{resource.accessories_included.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No accessories are listed.</p>}
              {resource.condition_notes && <p><strong>Condition notes:</strong> {resource.condition_notes}</p>}
              <p className="helper">Report any fault or change in condition to the manager.</p>
            </article>
          </div>
        </details>

        <details className="resource-disclosure" id="resource-requirements">
          <summary><span>Requirements and eligibility</span><small>Training, supervision, and your current checks</small></summary>
          <div className="resource-disclosure-content detail-layout">
            <article className="panel">
              <h2>Requirements</h2>
              <div className="tag-list">
                <Badge tone={supervisionRequired ? "warning" : "neutral"}>
                  {supervisionRequired ? "Supervision required" : "No supervision required"}
                </Badge>
                {(requirements?.training_codes ?? resource.required_training).map((code) => <Badge tone="info" key={code}>{code}</Badge>)}
              </div>
              {resource.supervised_windows.length > 0
                ? <><h3>Supervised windows (IST)</h3><ul className="simple-list">{resource.supervised_windows.map((window, index) => <li key={`${window.weekday}-${index}`}>{formatWindow(window)}</li>)}</ul></>
                : <p className="muted">No supervised windows are listed.</p>}
              {resource.required_training.length > 0 && <><h3>Required training</h3><ul className="simple-list">{resource.required_training.map((entry) => <li key={entry}>{entry}</li>)}</ul></>}
            </article>
            <article className="panel">
              <h2>Your current checks</h2>
              {eligibility.length > 0 ? (
                <ul className="eligibility-list">
                  {eligibility.map((item, index) => (
                    <li className={item.passed ? "eligibility-pass" : "eligibility-fail"} key={`${item.code ?? item.requirement}-${index}`}>
                      <span className="eligibility-icon" aria-hidden="true">{item.passed ? "✓" : "!"}</span>
                      <div><strong>{item.requirement}</strong><p>{item.message}</p>{!item.passed && <p><strong>Next step:</strong> {item.next_action}</p>}</div>
                      <span className="sr-only">{item.passed ? "Pass" : "Fail"}</span>
                    </li>
                  ))}
                </ul>
              ) : <p>Choose a session time in the request form to check your eligibility for that slot.</p>}
              <p className="helper">The manager reviews every eligible request. The service checks eligibility again when you submit.</p>
            </article>
          </div>
        </details>

        <details className="resource-disclosure">
          <summary><span>Hours and booking conditions</span><small>Opening hours, next availability, and booking limits</small></summary>
          <div className="resource-disclosure-content detail-layout">
            <article className="panel">
              <h2>Operating hours (IST)</h2>
              {operatingHours.length ? <ul className="simple-list">{operatingHours.map((window, index) => <li key={`${window.weekday}-${index}`}>{formatWindow(window)}</li>)}</ul> : <p>No operating hours are listed by the service.</p>}
              {availabilityError !== null ? <ErrorState error={availabilityError} /> : <p><strong>Next available time:</strong> {nextAvailability ? formatIST(nextAvailability) : "Not currently provided"}</p>}
              <p className="helper">Other users’ bookings are not shown. The server checks conflicts when you submit.</p>
              {resource.hold_reason && <p className="alert alert-warning"><strong>Maintenance hold</strong>{resource.hold_reason}{resource.hold_review_date && ` Review date: ${resource.hold_review_date}.`}</p>}
            </article>
            <article className="panel">
              <h2>Booking conditions</h2>
              <dl className="resource-detail-facts">
                <div><dt>Maximum session</dt><dd>{resource.max_session_hours !== null ? `${resource.max_session_hours} hours` : "Not specified"}</dd></div>
                <div><dt>Maximum duration</dt><dd>{resource.max_duration_minutes !== null ? `${resource.max_duration_minutes} minutes` : "Not specified"}</dd></div>
                <div><dt>Advance booking window</dt><dd>{resource.advance_booking_window !== null ? `${resource.advance_booking_window} days` : "Not specified"}</dd></div>
                <div><dt>Cancellation cutoff</dt><dd>{resource.cancellation_cutoff} hours before the start</dd></div>
                <div><dt>Booking model</dt><dd>{resource.exclusive_booking ? "Exclusive booking" : "Shared capacity"}</dd></div>
              </dl>
            </article>
          </div>
        </details>

        <details
          className="resource-disclosure"
          onToggle={(event) => setHistoryExpanded(event.currentTarget.open)}
        >
          <summary><span>History</span><small>Sample session and incident counts</small></summary>
          <div className="resource-disclosure-content panel" id="resource-panel-history">
            {historyLoading && <Loading label="Loading resource history…" />}
            {historyError !== null && <ErrorState error={historyError} />}
            {memory && (
              <>
                <div className="history-summary">
                  <article><span>Completed sessions recorded</span><strong>{completedSessions}</strong>{memory.demo_data && <small>DEMO DATA — not live institutional statistics</small>}</article>
                  <article><span>Unresolved incidents</span><strong>{memory.metrics.unresolved_incidents}</strong>{memory.demo_data && <small>DEMO DATA — not live institutional statistics</small>}</article>
                  <article><span>Incident reports opened</span><strong>{incidentCount}</strong>{memory.demo_data && <small>DEMO DATA — not live institutional statistics</small>}</article>
                </div>
                <p className="helper">Counts come from the resource audit timeline and Resource Memory API. Only unresolved incidents are counted as current open incidents.</p>
              </>
            )}
            {!historyLoading && !historyError && timeline.length === 0 && memory && <EmptyState>No completed sessions or incident events were returned for this resource.</EmptyState>}
          </div>
        </details>
      </div>

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
                  <h3>3. Review and submit</h3>
                  <dl className="request-details">
                    <div><dt>Resource</dt><dd>{resource.name}</dd></div>
                    <div><dt>Institution</dt><dd>{resource.organization_name} · {resource.city}</dd></div>
                    <div><dt>Requested window (IST)</dt><dd>{formatIST(istInputToISO(startAt))} – {formatIST(istInputToISO(endAt))}</dd></div>
                    <div><dt>Purpose</dt><dd>{statusLabel(purpose)}</dd></div>
                  </dl>
                  <h4>Requirements for this time</h4>
                  {eligibility.length ? <ul className="eligibility-list">{eligibility.map((item, index) => <li className={item.passed ? "eligibility-pass" : "eligibility-fail"} key={`${item.code ?? item.requirement}-${index}`}><span className="eligibility-icon" aria-hidden="true">{item.passed ? "✓" : "!"}</span><div><strong>{item.requirement}</strong><p>{item.message}</p>{!item.passed && <p><strong>Next action:</strong> {item.next_action}</p>}</div></li>)}</ul> : <p>The service did not return a separate eligibility checklist. Submission will be evaluated by the backend.</p>}
                  <p className="helper">The backend checks eligibility again when you submit. The resource owner or manager makes the decision.</p>
                  <label className="agreement-check"><input type="checkbox" checked={agreed} onChange={(event) => setAgreed(event.target.checked)} /><span>I have reviewed the resource rules and safety notes and agree to follow them during any approved session.</span></label>
                  {eligibilityError !== null && <ErrorState error={eligibilityError} />}
                  {requestError !== null && <ErrorState error={requestError} />}
                  <div className="card-actions"><button className="button button-secondary" type="button" onClick={() => setStep(2)} disabled={submitting}>Back</button><button className="button button-primary" type="submit" disabled={submitting || !agreed}>{submitting ? "Submitting…" : "Submit for review"}</button></div>
                </section>
              )}
              {step < 3 && eligibilityError !== null && <ErrorState error={eligibilityError} />}
            </form>
          )}
        </section>
      )}
    </>
  );
}
