import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Badge, Button, Card, Input, Select, Textarea } from "../components/UI";
import { EmptyState, ErrorState, Loading } from "../components/Feedback";
import { PageHeading, StatusBadge } from "../components/PageHeading";

interface Resource {
  id: string;
  owner_id: string;
  name: string;
  category: string;
  short_summary: string;
  description: string;
  capability_tags: string[];
  location: string;
  building: string;
  room: string;
  address_note: string;
  status: string;
  hold_reason: string | null;
  hold_review_date: string | null;
  operating_hours: { weekday: number; start: string; end: string }[];
  capacity: number | null;
  quantity: number | null;
  allowed_uses: string[];
  who_can_use: string[];
  required_training: string[];
  supervision_required: boolean;
  supervised_windows: { weekday: number; start: string; end: string }[];
  usage_rules: string[];
  safety_notes: string[];
  max_session_hours: number | null;
  max_duration_minutes: number | null;
  advance_booking_window: number | null;
  cancellation_cutoff: number;
  accessories_included: string[];
  condition_notes: string;
  exclusive_booking: boolean;
  is_demo: boolean;
}

interface ResourceForm {
  [key: string]: string | boolean;
  name: string;
  category: string;
  short_summary: string;
  description: string;
  capability_tags: string;
  building: string;
  room: string;
  location: string;
  address_note: string;
  operating_hours: string;
  capacity: string;
  quantity: string;
  allowed_uses: string;
  who_can_use: string;
  required_training: string;
  supervision_required: boolean;
  supervised_windows: string;
  usage_rules: string;
  safety_notes: string;
  max_session_hours: string;
  advance_booking_window: string;
  cancellation_cutoff: string;
  accessories_included: string;
  condition_notes: string;
  status: string;
  hold_reason: string;
  hold_review_date: string;
  exclusive_booking: boolean;
  policy_change_reason: string;
}

interface WeeklyWindow {
  weekday: number;
  start: string;
  end: string;
}

const emptyForm = (): ResourceForm => ({
  name: "", category: "", short_summary: "", description: "", capability_tags: "",
  building: "", room: "", location: "", address_note: "", operating_hours: "[]", capacity: "",
  quantity: "", allowed_uses: "project\ncoursework\nresearch", who_can_use: "",
  required_training: "", supervision_required: false, supervised_windows: "[]",
  usage_rules: "", safety_notes: "", max_session_hours: "", advance_booking_window: "",
  cancellation_cutoff: "2", accessories_included: "", condition_notes: "",
  status: "active", hold_reason: "", hold_review_date: "", exclusive_booking: true,
  policy_change_reason: "",
});

function formFromResource(resource: Resource): ResourceForm {
  return {
    name: resource.name,
    category: resource.category,
    short_summary: resource.short_summary,
    description: resource.description,
    capability_tags: resource.capability_tags.join("\n"),
    building: resource.building,
    room: resource.room,
    location: resource.location,
    address_note: resource.address_note,
    operating_hours: JSON.stringify(resource.operating_hours, null, 2),
    capacity: resource.capacity?.toString() ?? "",
    quantity: resource.quantity?.toString() ?? "",
    allowed_uses: resource.allowed_uses.join("\n"),
    who_can_use: resource.who_can_use.join("\n"),
    required_training: resource.required_training.join("\n"),
    supervision_required: resource.supervision_required,
    supervised_windows: JSON.stringify(resource.supervised_windows, null, 2),
    usage_rules: resource.usage_rules.join("\n"),
    safety_notes: resource.safety_notes.join("\n"),
    max_session_hours: resource.max_session_hours?.toString()
      ?? (resource.max_duration_minutes === null ? "" : (resource.max_duration_minutes / 60).toString()),
    advance_booking_window: resource.advance_booking_window?.toString() ?? "",
    cancellation_cutoff: resource.cancellation_cutoff.toString(),
    accessories_included: resource.accessories_included.join("\n"),
    condition_notes: resource.condition_notes,
    status: resource.status,
    hold_reason: resource.hold_reason ?? "",
    hold_review_date: resource.hold_review_date ?? "",
    exclusive_booking: resource.exclusive_booking,
    policy_change_reason: "",
  };
}

function lines(value: string): string[] {
  return value.split(/\r?\n/).map((part) => part.trim()).filter(Boolean);
}

function windows(value: string): WeeklyWindow[] {
  const parsed: unknown = JSON.parse(value || "[]");
  if (!Array.isArray(parsed) || !parsed.every(isWeeklyWindow)) {
    throw new Error("Weekly hours must be an array of weekday/start/end objects.");
  }
  return parsed;
}

function isWeeklyWindow(value: unknown): value is WeeklyWindow {
  if (typeof value !== "object" || value === null) return false;
  if (!("weekday" in value) || !("start" in value) || !("end" in value)) return false;
  return typeof value.weekday === "number"
    && Number.isInteger(value.weekday)
    && value.weekday >= 1
    && value.weekday <= 7
    && typeof value.start === "string"
    && /^([01]\d|2[0-3]):[0-5]\d$/.test(value.start)
    && typeof value.end === "string"
    && /^([01]\d|2[0-3]):[0-5]\d$/.test(value.end)
    && value.end > value.start;
}

function optionalNumber(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) throw new Error("Numeric fields must contain valid numbers.");
  return parsed;
}

export function ResourceManagementPage() {
  const { user } = useAuth();
  const [resources, setResources] = useState<Resource[]>([]);
  const [selected, setSelected] = useState<Resource | null>(null);
  const [form, setForm] = useState<ResourceForm>(emptyForm);
  const [showPreview, setShowPreview] = useState(false);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.get<{ items: { id: string }[] }>("/resources");
      const details = await Promise.all(
        list.items.map(({ id }) => api.get<{ resource: Resource }>(`/resources/${id}`)),
      );
      setResources(details.map((item) => item.resource).filter((item) => item.owner_id === user?.id));
    } catch (loadError) {
      setError(loadError);
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  useEffect(() => { void load(); }, [load]);

  function change<K extends keyof ResourceForm>(key: K, value: ResourceForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function edit(resource: Resource) {
    setSelected(resource);
    setForm(formFromResource(resource));
    setSaved("");
    setShowPreview(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function newResource() {
    setSelected(null);
    setForm(emptyForm());
    setSaved("");
    setShowPreview(false);
  }

  function prepareSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      windows(form.operating_hours);
      windows(form.supervised_windows);
      if (!form.policy_change_reason.trim()) throw new Error("Add a policy change reason before saving.");
      if (form.supervision_required && windows(form.supervised_windows).length === 0) {
        throw new Error("Add at least one supervised window when supervision is required.");
      }
      setShowPreview(true);
    } catch (validationError) {
      setError(validationError);
    }
  }

  function payload(): Record<string, unknown> {
    const body: Record<string, unknown> = {
      name: form.name.trim(),
      category: form.category.trim(),
      short_summary: form.short_summary.trim(),
      description: form.description.trim(),
      capability_tags: lines(form.capability_tags),
      building: form.building.trim(),
      room: form.room.trim(),
      location: form.location.trim(),
      address_note: form.address_note.trim(),
      operating_hours: windows(form.operating_hours),
      capacity: optionalNumber(form.capacity),
      quantity: optionalNumber(form.quantity),
      allowed_uses: lines(form.allowed_uses),
      who_can_use: lines(form.who_can_use),
      required_training: lines(form.required_training),
      supervision_required: form.supervision_required,
      supervised_windows: windows(form.supervised_windows),
      usage_rules: lines(form.usage_rules),
      safety_notes: lines(form.safety_notes),
      max_session_hours: optionalNumber(form.max_session_hours),
      advance_booking_window: optionalNumber(form.advance_booking_window),
      cancellation_cutoff: Number(form.cancellation_cutoff),
      accessories_included: lines(form.accessories_included),
      condition_notes: form.condition_notes.trim(),
      status: form.status,
      hold_reason: form.status === "maintenance_hold" ? form.hold_reason.trim() : null,
      hold_review_date: form.status === "maintenance_hold" ? form.hold_review_date : null,
      exclusive_booking: form.exclusive_booking,
      policy_change_reason: form.policy_change_reason.trim(),
    };
    if (form.capacity && form.quantity) throw new Error("Provide capacity or quantity, not both.");
    if (selected) {
      delete body.name;
      delete body.category;
      return body;
    }
    return body;
  }

  async function save() {
    setPending(true);
    setError(null);
    setSaved("");
    try {
      const body = payload();
      if (selected) {
        await api.patch(`/resources/${selected.id}`, body);
        setSaved("Resource updated. The backend created and activated a new policy version; existing Access Contracts are unchanged.");
      } else {
        await api.post("/resources", body);
        setSaved("Resource created.");
      }
      setShowPreview(false);
      await load();
    } catch (saveError) {
      setError(saveError);
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <PageHeading title="Resource management" description="Create and maintain resources owned by your account. Policy changes are versioned by the backend." />
      {error !== null && <ErrorState error={error} />}
      {saved && <p className="result-panel result-positive" role="status">{saved}</p>}
      <div className="management-layout">
        <section>
          <div className="card-title-row">
            <h2>Your resources</h2>
            <Button type="button" onClick={newResource}>List a resource</Button>
          </div>
          {loading ? <Loading label="Loading your resources…" /> : resources.length === 0 ? (
            <EmptyState>Resources you list will appear here.</EmptyState>
          ) : <div className="resource-management-list">
            {resources.map((resource) => (
              <Card key={resource.id} className="management-resource-card">
                <div className="card-title-row"><h3>{resource.name}</h3><StatusBadge value={resource.status} /></div>
                <p>{resource.category} · {[resource.building, resource.room].filter(Boolean).join(" · ") || resource.location}</p>
                {resource.is_demo && <Badge>Sample data</Badge>}
                <div className="card-actions">
                  <Button type="button" variant="secondary" onClick={() => edit(resource)}>Edit resource</Button>
                  <Link className="text-link" to={`/resources/${resource.id}/memory`}>Resource Memory →</Link>
                </div>
              </Card>
            ))}
          </div>}
        </section>

        <Card className="resource-editor">
          <h2>{selected ? `Edit ${selected.name}` : "List a resource"}</h2>
          <p className="helper">One item per line for list fields. Weekly hours use weekday numbers 1–7 and 24-hour times, for example <code>[{"{"}"weekday":1,"start":"09:00","end":"17:00"{"}"}]</code>.</p>
          <form onSubmit={prepareSave}>
            <fieldset>
              <legend>Basics</legend>
              <Input label="Name" required maxLength={160} value={form.name} onChange={(event) => change("name", event.target.value)} />
              <Input label="Category" required maxLength={80} value={form.category} onChange={(event) => change("category", event.target.value)} />
              <Input label="Short summary" maxLength={400} value={form.short_summary} onChange={(event) => change("short_summary", event.target.value)} />
              <Textarea label="Description" maxLength={8000} value={form.description} onChange={(event) => change("description", event.target.value)} />
              <Textarea label="Capability tags" value={form.capability_tags} onChange={(event) => change("capability_tags", event.target.value)} />
            </fieldset>
            <fieldset>
              <legend>Location and hours</legend>
              <Input label="Building" maxLength={160} value={form.building} onChange={(event) => change("building", event.target.value)} />
              <Input label="Room" maxLength={80} value={form.room} onChange={(event) => change("room", event.target.value)} />
              <Input label="Location label" maxLength={160} value={form.location} onChange={(event) => change("location", event.target.value)} helper="The backend can derive this from building and room when left blank." />
              <Textarea label="Address note" maxLength={1000} value={form.address_note} onChange={(event) => change("address_note", event.target.value)} />
              <Textarea label="Operating hours (JSON)" required value={form.operating_hours} onChange={(event) => change("operating_hours", event.target.value)} />
              <div className="form-grid">
                <Input label="Capacity" type="number" min="1" value={form.capacity} onChange={(event) => change("capacity", event.target.value)} />
                <Input label="Quantity" type="number" min="1" value={form.quantity} onChange={(event) => change("quantity", event.target.value)} />
              </div>
            </fieldset>
            <fieldset>
              <legend>Requirements and training</legend>
              <Textarea label="Allowed uses" required value={form.allowed_uses} onChange={(event) => change("allowed_uses", event.target.value)} helper="Allowed values: project, coursework, research." />
              <Textarea label="Who can use this resource" value={form.who_can_use} onChange={(event) => change("who_can_use", event.target.value)} />
              <Textarea label="Required training" value={form.required_training} onChange={(event) => change("required_training", event.target.value)} />
              <div className="form-grid">
                <Input label="Maximum session hours" type="number" min="0.1" max="168" step="0.1" value={form.max_session_hours} onChange={(event) => change("max_session_hours", event.target.value)} />
                <Input label="Advance booking window (days)" type="number" min="0" max="365" value={form.advance_booking_window} onChange={(event) => change("advance_booking_window", event.target.value)} />
              </div>
            </fieldset>
            <fieldset>
              <legend>Supervision</legend>
              <label className="checkbox-field"><input type="checkbox" checked={form.supervision_required} onChange={(event) => change("supervision_required", event.target.checked)} /> Supervision required</label>
              <Textarea label="Supervised windows (JSON)" value={form.supervised_windows} onChange={(event) => change("supervised_windows", event.target.value)} />
            </fieldset>
            <fieldset>
              <legend>Rules and safety</legend>
              <Textarea label="Usage rules" value={form.usage_rules} onChange={(event) => change("usage_rules", event.target.value)} />
              <Textarea label="Safety notes" value={form.safety_notes} onChange={(event) => change("safety_notes", event.target.value)} />
              <Textarea label="Condition notes" maxLength={2000} value={form.condition_notes} onChange={(event) => change("condition_notes", event.target.value)} />
              <Input label="Cancellation cutoff (hours)" type="number" min="0" max="720" step="0.5" required value={form.cancellation_cutoff} onChange={(event) => change("cancellation_cutoff", event.target.value)} />
            </fieldset>
            <fieldset>
              <legend>Accessories and status</legend>
              <Textarea label="Accessories included" value={form.accessories_included} onChange={(event) => change("accessories_included", event.target.value)} />
              <Select label="Resource status" value={form.status} onChange={(event) => change("status", event.target.value)}>
                <option value="active">Active</option><option value="maintenance_hold">Maintenance hold</option><option value="retired">Retired</option>
              </Select>
              {form.status === "maintenance_hold" && <>
                <Textarea label="Maintenance hold reason" required maxLength={2000} value={form.hold_reason} onChange={(event) => change("hold_reason", event.target.value)} />
                <Input label="Hold review date" type="date" required value={form.hold_review_date} onChange={(event) => change("hold_review_date", event.target.value)} />
              </>}
              <label className="checkbox-field"><input type="checkbox" checked={form.exclusive_booking} onChange={(event) => change("exclusive_booking", event.target.checked)} /> Exclusive booking</label>
            </fieldset>
            <fieldset>
              <legend>Policy preview and activation</legend>
              <Textarea label="Policy change reason" required maxLength={2000} value={form.policy_change_reason} onChange={(event) => change("policy_change_reason", event.target.value)} helper="Saved to the policy audit event. Existing Access Contract snapshots are not modified." />
            </fieldset>
            <div className="card-actions">
              <Button type="submit" disabled={pending}>{selected ? "Preview changes" : "Preview resource"}</Button>
              {selected && <Button type="button" variant="quiet" onClick={newResource}>Cancel edit</Button>}
            </div>
          </form>
          {showPreview && (
            <section className="policy-preview" aria-labelledby="policy-preview-title">
              <h3 id="policy-preview-title">Review before activation</h3>
              <p>Saving these changes will immediately activate a new policy version. Older Access Contracts remain unchanged.</p>
              <dl className="request-details">
                <div><dt>Allowed uses</dt><dd>{lines(form.allowed_uses).join(", ") || "None entered"}</dd></div>
                <div><dt>Required training</dt><dd>{lines(form.required_training).join(", ") || "None"}</dd></div>
                <div><dt>Supervision</dt><dd>{form.supervision_required ? `Required (${windows(form.supervised_windows).length} windows)` : "Not required"}</dd></div>
                <div><dt>Reason</dt><dd>{form.policy_change_reason}</dd></div>
              </dl>
              <div className="card-actions">
                <Button type="button" disabled={pending} onClick={() => void save()}>{pending ? "Saving…" : "Confirm and activate"}</Button>
                <Button type="button" variant="secondary" onClick={() => setShowPreview(false)} disabled={pending}>Back to edit</Button>
              </div>
            </section>
          )}
        </Card>
      </div>
    </>
  );
}
