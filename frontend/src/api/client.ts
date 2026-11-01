import type { APIErrorDetail, APIErrorPayload } from "./types";

const API_BASE = import.meta.env.VITE_API_URL?.replace(/\/$/, "") || "/api";

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: APIErrorDetail[];
  readonly requestId?: string;

  constructor(
    status: number,
    code: string,
    message: string,
    details: APIErrorDetail[] = [],
    requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  get displayMessage(): string {
    const mapped: Record<string, string> = {
      ineligible: "This request is not eligible. Review the blockers below.",
      conflict: "This action conflicts with the current schedule or record.",
      forbidden: "You do not have permission to complete this action.",
      invalid_state: "This action is not available in the record’s current state.",
      validation_error: "Some information needs attention.",
    };
    const heading = mapped[this.code];
    return heading && this.message ? `${heading} ${this.message}` : this.message;
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body !== undefined) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...options,
      headers,
      credentials: "include",
      body:
        options.body === undefined
          ? undefined
          : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(
      0,
      "network_error",
      "The backend could not be reached. Check the connection and try again.",
    );
  }

  const isPublicAuthRequest = [
    "/auth/session",
    "/auth/login",
    "/auth/register",
    "/auth/demo-login",
  ].includes(path);
  if (response.status === 401 && !isPublicAuthRequest) {
    if (window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
    throw new ApiError(401, "forbidden", "Your session has ended. Please sign in again.");
  }

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as APIErrorPayload;
    throw new ApiError(
      response.status,
      payload.error?.code || "request_error",
      payload.error?.message || `Request failed (${response.status}).`,
      payload.error?.details || [],
      payload.error?.request_id,
    );
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown, headers?: HeadersInit) =>
    request<T>(path, { method: "POST", body, headers }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body }),
};
