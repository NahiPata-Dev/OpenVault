import { CheckCircle2, CircleHelp, CircleX } from "lucide-react";

export function PageHeader({
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

export const PageHeading = PageHeader;

export function StatusBadge({ value, ready }: { value: string; ready?: boolean }) {
  const states = value.toLowerCase().split(/[_.\s-]+/);
  const isPositive = states.some((state) => ["active", "approved", "confirmed", "closed", "complete", "completed", "ready", "resolved", "returned", "passed"].includes(state));
  const isNegative = states.some((state) => ["blocked", "cancelled", "incident", "rejected", "retired", "failed", "ineligible", "maintenance", "expired"].includes(state));
  const stateClass = ready === undefined ? "" : ready ? "status-ready" : "status-blocked";
  const label = ready === undefined ? value.replaceAll("_", " ") : ready ? "Ready" : "Not ready";
  const className = stateClass || (isPositive ? "status-ready" : isNegative ? "status-blocked" : "");
  const Icon = ready === undefined
    ? isPositive ? CheckCircle2 : isNegative ? CircleX : CircleHelp
    : ready ? CheckCircle2 : CircleX;
  return <span className={`status-badge ${className}`}><Icon size={14} aria-hidden="true" />{label}</span>;
}
