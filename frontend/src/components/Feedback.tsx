import type { ReactNode } from "react";
import { ApiError } from "../api/client";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <p className="feedback" role="status" aria-live="polite">
      {label}
    </p>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="feedback">{children}</p>;
}

export function ErrorState({ error }: { error: unknown }) {
  const apiError =
    error instanceof ApiError
      ? error
      : new ApiError(0, "unknown", error instanceof Error ? error.message : "Something went wrong.");
  return (
    <div className="error-box" role="alert">
      <strong>{apiError.displayMessage}</strong>
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
    </div>
  );
}
