import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Role } from "../api/types";
import { ErrorState } from "./Feedback";
import { formatIST, statusLabel } from "../lib/format";

interface AssistantSuggestion {
  resource_id: string;
  reason: string;
}

interface AssistantEligibilityItem {
  requirement: string;
  status: "pass" | "fail";
  next_action: string;
}

interface AssistantEligibility {
  resource_id: string;
  items: AssistantEligibilityItem[];
}

interface AssistantDraft {
  resource_id: string;
  start: string;
  end: string;
  purpose: string;
  allowed_use: "project" | "coursework" | "research";
}

interface AssistantResponse {
  reply_text: string;
  suggestions: AssistantSuggestion[];
  eligibility: AssistantEligibility[];
  draft_request: AssistantDraft | null;
  quick_actions: string[];
  source: "model" | "rules";
  request_id: string;
}

interface ResourceDetailResponse {
  resource: {
    id: string;
    name: string;
    organization_name: string;
    city: string;
  };
}

interface SuggestedResource extends AssistantSuggestion {
  name: string;
  organization_name: string;
  city: string;
  eligibility: AssistantEligibilityItem[];
}

interface RequestResult {
  request: { id: string; status: string };
  eligibility: {
    eligible: boolean;
    blockers: { code: string; message: string; next_action: string }[];
  };
}

interface AssistantMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: AssistantResponse;
  resources?: SuggestedResource[];
  draftResourceName?: string;
  submission?: RequestResult;
}

function messageId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

function draftEditUrl(draft: AssistantDraft): string {
  const params = new URLSearchParams({
    assistantDraft: "1",
    start: draft.start,
    end: draft.end,
    purpose: draft.allowed_use,
  });
  return `/resources/${draft.resource_id}?${params.toString()}#request-title`;
}

function eligibilitySummary(items: AssistantEligibilityItem[]): string {
  if (items.length === 0) return "Not checked";
  const passed = items.filter((item) => item.status === "pass").length;
  const failed = items.length - passed;
  return `${passed} passed · ${failed} ${failed === 1 ? "issue" : "issues"}`;
}

export function BookingAssistant({ role }: { role: Role }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [retryMessage, setRetryMessage] = useState<string | null>(null);
  const [confirmingMessageId, setConfirmingMessageId] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const canChat = role === "requester" || role === "lab_manager";

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleEscape(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        toggleRef.current?.focus();
      }
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [open]);

  useEffect(() => {
    if (open && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, busy, error, open]);

  async function sendMessage(message: string) {
    const trimmed = message.trim();
    if (!canChat || !trimmed || busy) return;
    const userMessage: AssistantMessage = {
      id: messageId(),
      role: "user",
      text: trimmed,
    };
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setBusy(true);
    setError(null);
    setRetryMessage(null);
    try {
      const response = await api.post<AssistantResponse>("/assistant/chat", {
        message: trimmed,
      });
      const resourceIds = [
        ...new Set([
          ...response.suggestions.map((suggestion) => suggestion.resource_id),
          ...(response.draft_request ? [response.draft_request.resource_id] : []),
        ]),
      ];
      const resourceDetails = new Map(
        await Promise.all(
          resourceIds.map(async (resourceId) => {
            const detail = await api.get<ResourceDetailResponse>(`/resources/${resourceId}`);
            return [resourceId, detail.resource] as const;
          }),
        ),
      );
      const details = response.suggestions.map(
        (suggestion) => {
          const resource = resourceDetails.get(suggestion.resource_id);
          if (!resource) throw new Error("A suggested resource could not be loaded.");
          const eligibility =
            response.eligibility.find(
              (item) => item.resource_id === suggestion.resource_id,
            )?.items ?? [];
          return {
            ...suggestion,
            name: resource.name,
            organization_name: resource.organization_name,
            city: resource.city,
            eligibility,
          };
        },
      );
      setMessages((current) => [
        ...current,
        {
          id: messageId(),
          role: "assistant",
          text: response.reply_text,
          response,
          resources: details,
          draftResourceName: response.draft_request
            ? resourceDetails.get(response.draft_request.resource_id)?.name
            : undefined,
        },
      ]);
    } catch (sendError) {
      setError(sendError);
      setRetryMessage(trimmed);
    } finally {
      setBusy(false);
    }
  }

  async function confirmDraft(message: AssistantMessage) {
    const draft = message.response?.draft_request;
    if (!draft || busy || confirmingMessageId) return;
    setBusy(true);
    setConfirmingMessageId(message.id);
    setError(null);
    setRetryMessage(null);
    try {
      const result = await api.post<RequestResult>("/requests", {
        resource_id: draft.resource_id,
        purpose: draft.purpose,
        start_at: draft.start,
        end_at: draft.end,
        assistant_draft: true,
      });
      setMessages((current) =>
        current.map((item) =>
          item.id === message.id ? { ...item, submission: result } : item,
        ),
      );
    } catch (submitError) {
      setError(submitError);
      setRetryMessage(null);
    } finally {
      setConfirmingMessageId(null);
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(input);
  }

  function onInputKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!busy && input.trim()) void sendMessage(input);
    }
  }

  return (
    <div className="booking-assistant">
      {open && (
        <section
          id="assistant-panel"
          className="assistant-panel"
          role="dialog"
          aria-modal="false"
          aria-labelledby="assistant-title"
        >
          <header className="assistant-header">
            <div>
              <h2 id="assistant-title">Booking assistant</h2>
              <p>The assistant helps you find and prepare requests. A person reviews every request.</p>
            </div>
            <button
              className="assistant-close"
              type="button"
              aria-label="Close booking assistant"
              onClick={() => {
                setOpen(false);
                toggleRef.current?.focus();
              }}
            >
              ×
            </button>
          </header>

          <div className="assistant-messages" ref={listRef} aria-live="polite">
            {!canChat ? (
              <p className="assistant-intro" role="status">
                Chat is available to requesters and lab managers. This account can browse the workspace but cannot use the booking assistant.
              </p>
            ) : messages.length === 0 ? (
              <p className="assistant-intro">
                Ask about resources, requirements, your request history, or prepare a request draft.
              </p>
            ) : (
              messages.map((message) => (
                <article
                  className={`assistant-message assistant-message-${message.role}`}
                  key={message.id}
                >
                  <p>{message.text}</p>
                  {message.response && (
                    <>
                      <span className="assistant-source">
                        {message.response.source === "model"
                          ? "Powered by AI model"
                          : "Powered by rules"}
                      </span>
                      {message.resources && message.resources.length > 0 && (
                        <div className="assistant-suggestions">
                          {message.resources.map((resource) => (
                            <article
                              className="assistant-resource-card"
                              key={resource.resource_id}
                            >
                              <strong>{resource.name}</strong>
                              <span>{resource.organization_name}</span>
                              <span>{resource.city}</span>
                              <span
                                className={
                                  resource.eligibility.some(
                                    (item) => item.status === "fail",
                                  )
                                    ? "assistant-eligibility-fail"
                                    : "assistant-eligibility-pass"
                                }
                              >
                                {eligibilitySummary(resource.eligibility)}
                              </span>
                              <Link
                                className="assistant-card-link"
                                to={`/resources/${resource.resource_id}`}
                                onClick={() => setOpen(false)}
                              >
                                View details
                              </Link>
                            </article>
                          ))}
                        </div>
                      )}
                      {message.response.draft_request && (
                        <section className="assistant-draft-card" aria-label="Draft request">
                          <h3>Draft request</h3>
                          <dl>
                            <div><dt>Resource</dt><dd>{message.draftResourceName ?? "Selected resource"}</dd></div>
                            <div><dt>Start</dt><dd>{formatIST(message.response.draft_request.start)}</dd></div>
                            <div><dt>End</dt><dd>{formatIST(message.response.draft_request.end)}</dd></div>
                            <div><dt>Purpose</dt><dd>{message.response.draft_request.purpose}</dd></div>
                            <div><dt>Allowed use</dt><dd>{message.response.draft_request.allowed_use}</dd></div>
                          </dl>
                          {message.submission ? (
                            <RequestSubmissionResult result={message.submission} />
                          ) : (
                            <div className="assistant-draft-actions">
                              <Link
                                className="assistant-card-link"
                                to={draftEditUrl(message.response.draft_request)}
                                onClick={() => setOpen(false)}
                              >
                                Edit
                              </Link>
                              <button
                                className="button button-primary"
                                type="button"
                                disabled={busy}
                                onClick={() => void confirmDraft(message)}
                              >
                                {confirmingMessageId === message.id
                                  ? "Submitting…"
                                  : "Confirm request"}
                              </button>
                            </div>
                          )}
                        </section>
                      )}
                      {message.response.quick_actions.length > 0 && (
                        <div className="assistant-quick-replies" aria-label="Suggested replies">
                          {message.response.quick_actions.map((action) => (
                            <button
                              key={action}
                              type="button"
                              disabled={busy || !canChat}
                              onClick={() => void sendMessage(action)}
                            >
                              {action}
                            </button>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                  {message.submission && !message.response?.draft_request && (
                    <RequestSubmissionResult result={message.submission} />
                  )}
                </article>
              ))
            )}
            {busy && (
              <p className="assistant-loading" role="status" aria-live="polite">
                {confirmingMessageId ? "Submitting your request…" : "Thinking…"}
              </p>
            )}
            {error !== null && (
              <div className="assistant-error" role="alert">
                <ErrorState error={error} />
                {retryMessage && (
                  <button
                    className="button button-secondary"
                    type="button"
                    disabled={busy}
                    onClick={() => void sendMessage(retryMessage)}
                  >
                    Retry
                  </button>
                )}
              </div>
            )}
          </div>

          <form className="assistant-composer" onSubmit={onSubmit}>
            <label className="sr-only" htmlFor="assistant-message">Message the booking assistant</label>
            <textarea
              id="assistant-message"
              ref={inputRef}
              rows={2}
              maxLength={500}
              value={input}
              disabled={!canChat || busy}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={onInputKeyDown}
              placeholder={canChat ? "Ask about resources or requests…" : "Assistant unavailable for this role"}
            />
            <div className="assistant-composer-footer">
              <span aria-live="polite">{input.length}/500</span>
              <button
                className="button button-primary"
                type="submit"
                disabled={!canChat || busy || !input.trim()}
              >
                Send
              </button>
            </div>
          </form>
        </section>
      )}
      <button
        ref={toggleRef}
        className="assistant-launcher"
        type="button"
        aria-expanded={open}
        aria-controls="assistant-panel"
        onClick={() => setOpen((current) => !current)}
      >
        <span aria-hidden="true">✦</span>
        <span>Booking assistant</span>
      </button>
    </div>
  );
}

function RequestSubmissionResult({ result }: { result: RequestResult }) {
  if (!result.eligibility.eligible) {
    return (
      <div className="assistant-result assistant-result-negative" role="status" aria-live="polite">
        <h4>INELIGIBLE</h4>
        <p>The request was saved, but the service found these blockers:</p>
        <ul>
          {result.eligibility.blockers.map((blocker, index) => (
            <li key={`${blocker.code}-${index}`}>
              <strong>{blocker.code.replaceAll("_", " ")}</strong>
              <span>{blocker.message}</span>
              <span><strong>Next action:</strong> {blocker.next_action}</span>
            </li>
          ))}
        </ul>
        <Link to="/requests">View my requests</Link>
      </div>
    );
  }
  return (
    <div className="assistant-result assistant-result-positive" role="status" aria-live="polite">
      <h4>Submitted — pending review</h4>
      <p>Your request is saved as {statusLabel(result.request.status)}. A person will review it; no booking is confirmed yet.</p>
      <Link to="/requests">View my requests</Link>
    </div>
  );
}
