export function PageHeading({
  eyebrow = "OPENVAULT",
  title,
  description,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
}) {
  return (
    <header className="page-heading">
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      {description && <p className="muted">{description}</p>}
    </header>
  );
}

export function StatusBadge({ value, ready }: { value: string; ready?: boolean }) {
  const stateClass = ready === undefined ? "" : ready ? "status-ready" : "status-blocked";
  const label = ready === undefined ? value.replaceAll("_", " ") : ready ? "Ready" : "Not ready";
  return <span className={`status-badge ${stateClass}`}>{label}</span>;
}
