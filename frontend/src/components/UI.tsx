import {
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

type ButtonVariant = "primary" | "secondary" | "quiet" | "danger";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return <button className={`button button-${variant} ${className}`} {...props} />;
}

interface FieldProps {
  label: string;
  helper?: string;
  error?: string;
  className?: string;
  required?: boolean;
}

function FieldFrame({
  label,
  helper,
  error,
  className,
  required,
  children,
}: FieldProps & { children: (ids: { inputId: string; describedBy?: string }) => ReactNode }) {
  const generatedId = useId();
  const inputId = `field-${generatedId}`;
  const helperId = helper ? `${inputId}-helper` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const describedBy = [helperId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={`field ${className ?? ""}`}>
      <label className="field-label" htmlFor={inputId}>
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      {children({ inputId, describedBy })}
      {helper && <p className="helper" id={helperId}>{helper}</p>}
      {error && <p className="field-error" id={errorId}>{error}</p>}
    </div>
  );
}

export function Input({
  label,
  helper,
  error,
  className = "",
  required,
  ...props
}: FieldProps & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <FieldFrame label={label} helper={helper} error={error} className={className} required={required}>
      {({ inputId, describedBy }) => (
        <input
          id={inputId}
          className={`input ${error ? "input-invalid" : ""}`}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          required={required}
          {...props}
        />
      )}
    </FieldFrame>
  );
}

export function Select({
  label,
  helper,
  error,
  className = "",
  required,
  children,
  ...props
}: FieldProps & SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <FieldFrame label={label} helper={helper} error={error} className={className} required={required}>
      {({ inputId, describedBy }) => (
        <select
          id={inputId}
          className={`select ${error ? "input-invalid" : ""}`}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          required={required}
          {...props}
        >
          {children}
        </select>
      )}
    </FieldFrame>
  );
}

export function Textarea({
  label,
  helper,
  error,
  className = "",
  required,
  ...props
}: FieldProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <FieldFrame label={label} helper={helper} error={error} className={className} required={required}>
      {({ inputId, describedBy }) => (
        <textarea
          id={inputId}
          className={`textarea ${error ? "input-invalid" : ""}`}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          required={required}
          {...props}
        />
      )}
    </FieldFrame>
  );
}

export function Card({
  children,
  className = "",
  as: Element = "section",
  ...props
}: {
  children: ReactNode;
  className?: string;
  as?: "article" | "section" | "div";
} & React.HTMLAttributes<HTMLElement>) {
  return <Element className={`card ${className}`} {...props}>{children}</Element>;
}

export function StatCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: ReactNode;
  detail?: string;
}) {
  return (
    <Card className="stat-card">
      <p className="stat-card-label">{label}</p>
      <strong className="stat-card-value">{value}</strong>
      {detail && <p className="stat-card-detail">{detail}</p>}
    </Card>
  );
}

type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info";

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: BadgeTone;
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Alert({
  children,
  title,
  tone = "info",
  className = "",
}: {
  children: ReactNode;
  title?: string;
  tone?: BadgeTone;
  className?: string;
}) {
  return (
    <div className={`alert alert-${tone} ${className}`} role={tone === "danger" ? "alert" : "status"}>
      {title && <strong>{title}</strong>}
      <div>{children}</div>
    </div>
  );
}

export function Modal({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={dialogRef}
      className="modal"
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialogRef.current) onClose();
      }}
    >
      <div className="modal-content">
        <div className="modal-heading">
          <h2 id={titleId}>{title}</h2>
          <Button type="button" variant="quiet" onClick={onClose} aria-label="Close dialog">Close</Button>
        </div>
        {children}
      </div>
    </dialog>
  );
}

export function Tabs({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: string; label: string }[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="tabs" role="tablist" aria-label="Profile sections">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          id={`tab-${tab.id}`}
          aria-selected={value === tab.id}
          aria-controls={`panel-${tab.id}`}
          tabIndex={value === tab.id ? 0 : -1}
          className="tab"
          onClick={() => onChange(tab.id)}
          onKeyDown={(event) => {
            if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
            event.preventDefault();
            const currentIndex = tabs.findIndex((item) => item.id === value);
            const direction = event.key === "ArrowRight" ? 1 : -1;
            const next = tabs[(currentIndex + direction + tabs.length) % tabs.length];
            onChange(next.id);
            document.getElementById(`tab-${next.id}`)?.focus();
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export function Table({
  headers,
  rows,
  caption,
}: {
  headers: string[];
  rows: ReactNode[][];
  caption: string;
}) {
  return (
    <div className="table-scroll">
      <table className="data-table">
        <caption>{caption}</caption>
        <thead><tr>{headers.map((header) => <th scope="col" key={header}>{header}</th>)}</tr></thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>{row.map((cell, cellIndex) => <td data-label={headers[cellIndex]} key={cellIndex}>{cell}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Skeleton({
  className = "",
  label = "Loading content",
  decorative = false,
}: {
  className?: string;
  label?: string;
  decorative?: boolean;
}) {
  return decorative
    ? <div className={`skeleton ${className}`} aria-hidden="true" />
    : <div className={`skeleton ${className}`} role="status" aria-label={label} />;
}

export function EmptyState({
  title = "Nothing to show yet",
  children,
  action,
}: {
  title?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-state-mark" aria-hidden="true">—</span>
      <h2>{title}</h2>
      <p>{children}</p>
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  );
}

export function Toast({
  message,
  onDismiss,
}: {
  message: string | null;
  onDismiss: () => void;
}) {
  useEffect(() => {
    if (!message) return;
    const timeout = window.setTimeout(onDismiss, 4500);
    return () => window.clearTimeout(timeout);
  }, [message, onDismiss]);
  if (!message) return null;
  return (
    <div className="toast" role="status" aria-live="polite">
      <span>{message}</span>
      <Button type="button" variant="quiet" onClick={onDismiss} aria-label="Dismiss notification">Dismiss</Button>
    </div>
  );
}

export function Stepper({
  steps,
  activeStep,
}: {
  steps: { title: string; description: string }[];
  activeStep?: number;
}) {
  return (
    <ol className="stepper">
      {steps.map((step, index) => (
        <li
          className={`stepper-item ${activeStep === index + 1 ? "stepper-current" : ""} ${activeStep !== undefined && index + 1 < activeStep ? "stepper-complete" : ""}`}
          key={step.title}
          aria-current={activeStep === index + 1 ? "step" : undefined}
        >
          <span className="stepper-number" aria-label={`Step ${index + 1}`}>{String(index + 1).padStart(2, "0")}</span>
          <div><h3>{step.title}</h3><p>{step.description}</p></div>
        </li>
      ))}
    </ol>
  );
}

export function useToast() {
  const [message, setMessage] = useState<string | null>(null);
  const dismiss = () => setMessage(null);
  return { message, show: setMessage, dismiss };
}
