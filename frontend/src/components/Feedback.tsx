import type { ReactNode } from "react";
import { ApiError } from "../api/client";
import { Alert, Button, EmptyState as UIEmptyState, Skeleton } from "./UI";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="loading-feedback">
      <Skeleton className="loading-skeleton" decorative />
      <span role="status" aria-live="polite">{label}</span>
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return <UIEmptyState title={title} action={action}>{children}</UIEmptyState>;
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const apiError =
    error instanceof ApiError
      ? error
      : new ApiError(0, "unknown", error instanceof Error ? error.message : "Something went wrong.");
  return (
    <Alert tone="danger" title={apiError.displayMessage}>
      {apiError.details.length > 0 && (
        <ul className="mt-2 list-disc pl-5">
          {apiError.details.map((detail, index) => (
            <li key={`${detail.code}-${index}`}>
              <span className="font-semibold">{detail.code}:</span> {detail.message}
            </li>
          ))}
        </ul>
      )}
      {apiError.requestId && (
        <p className="mt-2 text-sm">Reference: {apiError.requestId}</p>
      )}
      {onRetry && <Button type="button" variant="secondary" className="mt-3" onClick={onRetry}>Try again</Button>}
    </Alert>
  );
}
