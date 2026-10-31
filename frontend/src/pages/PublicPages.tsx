import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError, api, apiUrl } from "../api/client";
import type { DemoAccount, Role } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { PageHeading } from "../components/PageHeading";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  Tabs,
  Textarea,
  Toast,
  useToast,
} from "../components/UI";

const roleLabels: Record<Role, string> = {
  requester: "Requester",
  lab_manager: "Resource owner",
  institution_admin: "Institution admin",
  auditor: "Judge auditor",
};

interface ChatResource {
  resource_id: string;
  name: string;
  location: string;
  ready: boolean;
  explanation: string;
}

interface AIChatResponse {
  reply: string;
  resources: ChatResource[];
  disclosure: string;
}

interface AssistantMessage {
  role: "user" | "assistant";
  text: string;
}

function errorText(error: unknown): string {
  return error instanceof ApiError
    ? error.displayMessage
    : error instanceof Error
      ? error.message
      : "Something went wrong. Try again.";
}

function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {};
  return Object.fromEntries(
    error.details.flatMap((detail) => {
      const separator = detail.message.indexOf(":");
      if (separator < 0) return [];
      const field = detail.message.slice(0, separator).split(".").at(-1) ?? "";
      return field ? [[field, detail.message.slice(separator + 1).trim()]] : [];
    }),
  );
}

export function LandingPage() {
  const { user } = useAuth();
  const browsePath = user ? "/resources" : "/login?next=%2Fresources";
  const [goal, setGoal] = useState("");
  const [conversation, setConversation] = useState<AssistantMessage[]>([]);
  const [aiAvailable, setAIAvailable] = useState<boolean | null>(null);
  const [matches, setMatches] = useState<ChatResource[]>([]);
  const [aiDisclosure, setAIDisclosure] = useState("");
  const [matchMessage, setMatchMessage] = useState("");
  const [matching, setMatching] = useState(false);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [feedbackSaving, setFeedbackSaving] = useState(false);
  const [feedbackError, setFeedbackError] = useState("");

  useEffect(() => {
    let active = true;
    void api.get<{ available: boolean }>("/ai/status").then(
      ({ available }) => active && setAIAvailable(available),
      () => active && setAIAvailable(false),
    );
    return () => { active = false; };
  }, []);

  async function processAssistantMessage(requestGoal: string, searchNow = false) {
    if (!requestGoal && !searchNow) {
      setMatchMessage("Send a message to continue the conversation.");
      return;
    }
    if (aiAvailable !== true) {
      setMatchMessage("AI chat is not configured for this deployment.");
      return;
    }
    setMatching(true);
    setMatches([]);
    setMatchMessage("");
    setFeedbackSent(false);
    setFeedbackError("");
    const userMessage = searchNow ? "Find matching resources for my plan." : requestGoal;
    const nextMessages = [
      ...conversation,
      { role: "user" as const, text: userMessage },
    ].slice(-16);
    try {
      const response = await api.post<AIChatResponse>("/ai/chat", {
        messages: nextMessages.map(({ role, text }) => ({ role, content: text })),
      });
      setMatches(response.resources);
      setAIDisclosure(response.disclosure);
      setConversation([
        ...nextMessages,
        { role: "assistant" as const, text: response.reply },
      ].slice(-12));
      setGoal("");
    } catch (error) {
      setMatchMessage(errorText(error));
    } finally {
      setMatching(false);
    }
  }

  function submitAssistantMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void processAssistantMessage(goal.trim());
  }

  function startFreshSearch() {
    setGoal("");
    setConversation([]);
    setMatches([]);
    setAIDisclosure("");
    setMatchMessage("");
    setFeedbackSent(false);
    setFeedbackError("");
  }

  async function sendMatchFeedback(isHelpful: boolean) {
    setFeedbackSaving(true);
    setFeedbackError("");
    try {
      await api.post("/feedback", { is_helpful: isHelpful });
      setFeedbackSent(true);
    } catch (error) {
      setFeedbackError(errorText(error));
    } finally {
      setFeedbackSaving(false);
    }
  }

  return (
    <div className="public-page">
      <header className="public-header">
        <Link className="brand" to="/" aria-label="OpenVault home">openvault<span aria-hidden="true">.</span></Link>
        <nav className="public-nav" aria-label="Public navigation">
          {user ? (
            <Link className="button button-secondary" to="/resources">Open workspace</Link>
          ) : (
            <>
              <Link to="/login">Sign in</Link>
              <Link className="button button-primary" to="/signup">Create account</Link>
            </>
          )}
        </nav>
      </header>

      <main>
        <section className="hero-section assistant-hero">
          <div className="assistant-intro">
            <p className="eyebrow"><span className="eyebrow-dot" /> OPENVAULT RESOURCE GUIDE</p>
            <h1>What are you working on?</h1>
            <p>Describe your project, class, or research. Find equipment and spaces that fit, with the requirements and next steps up front.</p>
          </div>
          <section className="resource-assistant" aria-labelledby="assistant-title">
            <div className="assistant-heading">
              <span className="assistant-mark" aria-hidden="true">O</span>
              <div><h2 id="assistant-title">Plan your next step</h2><p>Talk through your goal, then find resources when you're ready.</p></div>
            </div>
            {conversation.length > 0 && (
              <div className="assistant-chat-log" role="log" aria-label="Resource search conversation" aria-relevant="additions">
                <div className="assistant-chat-toolbar"><span>Search conversation</span><button type="button" onClick={startFreshSearch}>Start fresh</button></div>
                {conversation.map((message, index) => (
                  <div className={`assistant-chat-message assistant-chat-${message.role}`} key={`${index}-${message.role}`}>
                    <strong>{message.role === "user" ? "You" : "OpenVault guide"}</strong><p>{message.text}</p>
                  </div>
                ))}
              </div>
            )}
            <form onSubmit={submitAssistantMessage}>
              <label className="sr-only" htmlFor="resource-goal">{conversation.length ? "Chat with the resource guide or refine your plan" : "Describe what you want to work on"}</label>
              <textarea
                id="resource-goal"
                className="assistant-input"
                maxLength={2000}
                placeholder={conversation.length ? "Add a constraint, ask a question, or tell me what to refine…" : "Tell me what you're trying to make, learn, or solve…"}
                value={goal}
                onChange={(event) => setGoal(event.target.value)}
                disabled={matching || aiAvailable === false}
                aria-describedby="assistant-note"
              />
              <div className="assistant-compose-footer">
                <span id="assistant-note">{conversation.length ? "Your recent messages stay in this chat." : "A few details help shape a practical plan."}</span>
                <button className="button button-primary assistant-submit" type="submit" disabled={matching || aiAvailable !== true} aria-label="Send message">
                  {matching ? "Thinking…" : "Send message"}<span aria-hidden="true">→</span>
                </button>
              </div>
            </form>
            {aiAvailable === false && <p className="assistant-message" role="status">AI chat is not configured for this deployment. An administrator must configure a server-side model provider before chat can be used.</p>}
            {aiAvailable === true && <p className="assistant-disclosure">Your recent chat and relevant resource details are sent to the institution's configured AI provider to generate replies.</p>}
            <div className="assistant-prompts" aria-label={conversation.length ? "Suggested refinements" : "Example searches"}>
              <span>{conversation.length ? "Refine" : "Try"}</span>
              {(conversation.length ? ["Prefer Electronics Lab", "Find a camera instead", "Try a 3D printer"] : ["Prototype a 3D-printed part", "Capture a field study", "Run an electronics experiment"]).map((prompt) => (
                <button type="button" key={prompt} disabled={aiAvailable !== true} onClick={() => setGoal(prompt)}>{prompt}</button>
              ))}
            </div>
            {matching && <div className="assistant-thinking" role="status"><span className="assistant-typing" aria-hidden="true"><i /><i /><i /></span><span>Thinking through your plan and resource options</span></div>}
            {matchMessage && <p className="assistant-message" role="status">{matchMessage}</p>}
            {user && user.role === "auditor" && <p className="assistant-message" role="status">This account is read-only. You can still <Link to="/resources">browse the catalog</Link>.</p>}
            {conversation.length > 0 && matches.length === 0 && (
              <div className="assistant-search-next">
                <span>Ready to connect this plan to real options?</span>
                <button className="button button-secondary" type="button" disabled={matching || aiAvailable !== true} onClick={() => void processAssistantMessage("", true)}>
                  {matching ? "Checking options…" : "Find matching resources"}
                </button>
              </div>
            )}
            {matches.length > 0 && (
              <div className="assistant-results" aria-live="polite">
                <div className="assistant-results-heading"><h3>Good places to start</h3><Link to="/resources">Browse all resources</Link></div>
                {matches.map((resource) => (
                  <Link className="assistant-result" to={`/resources/${resource.resource_id}`} key={resource.resource_id}>
                    <span><strong>{resource.name}</strong><small>{resource.location}</small><small>{resource.ready ? "Readiness check: ready for evaluation" : "Readiness check: review requirements"}</small><small>{resource.explanation}</small></span>
                    <span className="assistant-result-arrow" aria-hidden="true">↗</span>
                  </Link>
                ))}
                <p className="assistant-disclosure">{aiDisclosure} Eligibility, availability, and approval are checked by OpenVault separately.</p>
                <div className="assistant-feedback">
                  {feedbackSent ? <p role="status">Thanks, your feedback was recorded.</p> : <>
                    <span>Were these matches useful?</span>
                    <button type="button" disabled={feedbackSaving} onClick={() => void sendMatchFeedback(true)}>Yes</button>
                    <button type="button" disabled={feedbackSaving} onClick={() => void sendMatchFeedback(false)}>Not quite</button>
                  </>}
                </div>
                {feedbackError && <p className="assistant-feedback-error" role="alert">{feedbackError}</p>}
              </div>
            )}
            {!user && matchMessage === "Sign in to get resource matches for your plan." && <Link className="button button-secondary assistant-login" to={`/login?next=${encodeURIComponent("/resources")}`}>Sign in to continue</Link>}
          </section>
          <div className="assistant-path" aria-label="How resource requests work">
            <span><b>01</b> Find a fit</span><i aria-hidden="true" />
            <span><b>02</b> Check requirements</span><i aria-hidden="true" />
            <span><b>03</b> Request a time</span><i aria-hidden="true" />
            <span><b>04</b> Owner reviews</span>
          </div>
          <div className="assistant-browse"><span>Prefer to explore?</span><Link to={browsePath}>Browse the full resource catalog <span aria-hidden="true">→</span></Link></div>
        </section>
      </main>
      <footer className="public-footer">
        <Link className="brand" to="/">openvault<span aria-hidden="true">.</span></Link>
        <p>Availability, eligibility and approvals depend on the institution. OpenVault does not replace local safety procedures or institutional policy.</p>
        <Link to="/privacy">Privacy and limitations</Link>
        <span>© OpenVault</span>
      </footer>
    </div>
  );
}

export function LoginPage() {
  const { accounts, accountsError, signIn, signInDemo } = useAuth();
  const [oauthProviders, setOauthProviders] = useState({ google: false, linkedin: false });
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [demoPassword, setDemoPassword] = useState("");
  const [showDemoPassword, setShowDemoPassword] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const nextPath = new URLSearchParams(location.search).get("next");
  const safeNextPath = nextPath?.startsWith("/") && !nextPath.startsWith("//") ? nextPath : "/resources";
  const oauthError = new URLSearchParams(location.search).get("oauth_error");
  const oauthErrorText: Record<string, string> = {
    provider_error: "The provider sign-in did not complete. Please try again.",
    provider_unavailable: "That sign-in provider is not configured.",
    unverified_email: "The provider did not return a verified email address.",
    account_not_found: "Create an OpenVault account with this verified email before using provider sign-in.",
    account_inactive: "This account is inactive. Contact your institution administrator.",
  };

  useEffect(() => {
    let active = true;
    void api.get<{ providers: typeof oauthProviders }>("/auth/providers").then(
      ({ providers }) => active && setOauthProviders(providers),
      () => active && setOauthProviders({ google: false, linkedin: false }),
    );
    return () => { active = false; };
  }, []);

  function startProviderSignIn(provider: "google" | "linkedin") {
    const query = new URLSearchParams({ next: safeNextPath });
    window.location.assign(apiUrl(`/auth/${provider}/start?${query.toString()}`));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await signIn(email.trim().toLowerCase(), password);
      navigate(safeNextPath, { replace: true });
    } catch (loginError) {
      setError(loginError);
    } finally {
      setPending(false);
    }
  }

  async function quickLogin(account: DemoAccount) {
    setPending(true);
    setError(null);
    try {
      await signInDemo(account.id, demoPassword);
      navigate(safeNextPath, { replace: true });
    } catch (loginError) {
      setError(loginError);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-aside">
        <Link className="brand brand-light" to="/">openvault<span aria-hidden="true">.</span></Link>
        <div><p className="eyebrow">SHARED ACCESS, CLEARLY MANAGED</p><h1>Make room for what’s next.</h1><p>Find institutional resources, understand the requirements and follow every decision.</p></div>
        <p className="auth-aside-foot">A resource coordination prototype for institutions.</p>
      </div>
      <section className="auth-panel" aria-labelledby="login-title">
        <div className="auth-form-wrap">
          <Link className="back-link" to="/">← Back to home</Link>
          <p className="eyebrow">WELCOME BACK</p>
          <h2 id="login-title">Sign in to OpenVault</h2>
          <p className="muted">Use your institutional account to continue.</p>
          {error !== null && <Alert tone="danger" title="We couldn’t sign you in">{errorText(error)}</Alert>}
          {oauthError && <Alert tone="danger" title="Provider sign-in failed">{oauthErrorText[oauthError] ?? "Please try signing in again."}</Alert>}
          {(oauthProviders.google || oauthProviders.linkedin) && (
            <div className="oauth-options" aria-label="Alternative sign-in methods">
              {oauthProviders.google && <button className="button button-secondary oauth-button" type="button" onClick={() => startProviderSignIn("google")}>Continue with Google</button>}
              {oauthProviders.linkedin && <button className="button button-secondary oauth-button" type="button" onClick={() => startProviderSignIn("linkedin")}>Continue with LinkedIn</button>}
              <p>Use a verified email already registered with OpenVault.</p>
            </div>
          )}
          <form onSubmit={(event) => void submit(event)} noValidate>
            <Input label="Email address" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
            <div className="password-field">
              <Input label="Password" type={showPassword ? "text" : "password"} autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
              <button type="button" className="password-toggle" onClick={() => setShowPassword((value) => !value)} aria-pressed={showPassword}>{showPassword ? "Hide" : "Show"}</button>
            </div>
            <div className="auth-links"><Link to="/login?forgot=1">Forgot password?</Link><Link to="/signup">Create an account</Link></div>
            {new URLSearchParams(location.search).has("forgot") && (
              <Alert className="forgot-note" title="Password reset isn’t available in this prototype">
                Please contact your institution administrator for help accessing your account.
              </Alert>
            )}
            <Button className="w-full button-large" type="submit" disabled={pending}>{pending ? "Signing in…" : "Sign in"}</Button>
          </form>

          <details className="quick-login">
            <summary>Judge quick login <span>Seeded sample accounts</span></summary>
            <div className="quick-login-body">
              <p className="helper">Demo accounts use the shared password provided by the institution.</p>
              <div className="password-field">
                <Input label="Shared demo password" type={showDemoPassword ? "text" : "password"} autoComplete="off" value={demoPassword} onChange={(event) => setDemoPassword(event.target.value)} />
                <button type="button" className="password-toggle" onClick={() => setShowDemoPassword((value) => !value)} aria-pressed={showDemoPassword}>{showDemoPassword ? "Hide" : "Show"}</button>
              </div>
              {accountsError && <Alert tone="warning">{accountsError}</Alert>}
              <div className="quick-account-list">
                {accounts.map((account) => (
                  <Button key={account.id} type="button" variant="secondary" className="quick-account" disabled={pending || !demoPassword} onClick={() => void quickLogin(account)}>
                    <span>{account.display_name}</span><Badge>{roleLabels[account.role]}</Badge>
                  </Button>
                ))}
                {accounts.length === 0 && !accountsError && <p className="helper">No seeded accounts are available.</p>}
              </div>
            </div>
          </details>
          <p className="auth-legal">By continuing, you agree to follow your institution’s access and safety requirements.</p>
        </div>
      </section>
    </main>
  );
}

export function SignupPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organization, setOrganization] = useState("");
  const [intendedUse, setIntendedUse] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<unknown>(null);
  const [created, setCreated] = useState(false);
  const [pending, setPending] = useState(false);
  const navigate = useNavigate();
  const strength = password.length === 0 ? 0 : Math.min(4, Number(password.length >= 10) + Number(/[a-z]/.test(password) && /[A-Z]/.test(password)) + Number(/\d/.test(password)) + Number(/[^A-Za-z0-9]/.test(password)));

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: Record<string, string> = {};
    if (!fullName.trim()) nextErrors.full_name = "Enter your full name.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) nextErrors.email = "Enter a valid email address.";
    if (password.length < 10) nextErrors.password = "Use at least 10 characters.";
    else if (/^\d+$/.test(password)) nextErrors.password = "Password cannot contain only digits.";
    if (!acceptedTerms) nextErrors.terms = "Please confirm you have read the terms and privacy note.";
    setErrors(nextErrors);
    setServerError(null);
    if (Object.keys(nextErrors).length) return;
    setPending(true);
    try {
      await api.post("/auth/register", {
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        password,
        organization_name: organization.trim() || null,
        intended_use: intendedUse.trim() || null,
      });
      setCreated(true);
    } catch (signupError) {
      setServerError(signupError);
      setErrors(fieldErrors(signupError));
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-aside">
        <Link className="brand brand-light" to="/">openvault<span aria-hidden="true">.</span></Link>
        <div><p className="eyebrow">YOUR NEXT PROJECT STARTS HERE</p><h1>One account. A clearer path to access.</h1><p>Set up your profile to discover resources and submit a request to your institution.</p></div>
        <p className="auth-aside-foot">OpenVault does not approve access automatically. Resource owners make the final decision.</p>
      </div>
      <section className="auth-panel" aria-labelledby="signup-title">
        <div className="auth-form-wrap auth-form-wide">
          <Link className="back-link" to="/">← Back to home</Link>
          <p className="eyebrow">GET STARTED</p>
          <h2 id="signup-title">Create your account</h2>
          <p className="muted">Fields marked with * are required.</p>
          {created ? (
            <Alert tone="success" title="Account created">
              Your account is ready. Sign in with your email and password.
              <Button className="mt-4" type="button" onClick={() => navigate("/login", { replace: true })}>Continue to sign in</Button>
            </Alert>
          ) : (
            <>
              {serverError !== null && <Alert tone="danger" title="We couldn’t create your account">{errorText(serverError)}</Alert>}
              <form className="signup-form" onSubmit={(event) => void submit(event)} noValidate>
                <Input label="Full name" autoComplete="name" required maxLength={120} value={fullName} error={errors.full_name} onChange={(event) => setFullName(event.target.value)} />
                <Input label="Email address" type="email" autoComplete="email" required maxLength={254} value={email} error={errors.email} onChange={(event) => setEmail(event.target.value)} />
                <div className="password-field">
                  <Input label="Password" type={showPassword ? "text" : "password"} autoComplete="new-password" required minLength={10} maxLength={256} helper="At least 10 characters and not all digits." value={password} error={errors.password} onChange={(event) => setPassword(event.target.value)} />
                  <button type="button" className="password-toggle" onClick={() => setShowPassword((value) => !value)} aria-pressed={showPassword}>{showPassword ? "Hide" : "Show"}</button>
                </div>
                <div className="strength-meter" aria-label={`Password strength: ${["not set", "weak", "fair", "good", "strong"][strength]}`}>
                  <div className="strength-bars">{[1, 2, 3, 4].map((level) => <span className={strength >= level ? `strength-${strength}` : ""} key={level} />)}</div>
                  <span>{password ? `Strength: ${["", "weak", "fair", "good", "strong"][strength]}` : "Strength hint"}</span>
                </div>
                <Input label="Organization (optional)" autoComplete="organization" maxLength={200} value={organization} onChange={(event) => setOrganization(event.target.value)} />
                <Textarea label="What do you want to use OpenVault for? (optional)" maxLength={2000} rows={3} value={intendedUse} onChange={(event) => setIntendedUse(event.target.value)} />
                <label className="checkbox-row">
                  <input type="checkbox" checked={acceptedTerms} onChange={(event) => setAcceptedTerms(event.target.checked)} aria-invalid={Boolean(errors.terms)} />
                  <span>I have read the <Link to="/terms">terms</Link> and <Link to="/privacy">privacy note</Link>.</span>
                </label>
                {errors.terms && <p className="field-error">{errors.terms}</p>}
                <Button className="w-full button-large" type="submit" disabled={pending}>{pending ? "Creating account…" : "Create account"}</Button>
                <p className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></p>
              </form>
            </>
          )}
        </div>
      </section>
    </main>
  );
}

interface AccountProfile {
  id: string;
  full_name: string;
  email: string | null;
  organization_name: string | null;
  phone: string | null;
  intended_use: string | null;
  role: Role;
  status: "active" | "inactive";
}

interface OwnerApplication {
  id: string;
  organization: string;
  role_in_organization: string;
  reason: string;
  resources_to_list: string;
  status: "pending" | "approved" | "rejected";
  decision_reason: string | null;
  created_at: string;
}

export function ProfilePage() {
  const [profile, setProfile] = useState<AccountProfile | null>(null);
  const [application, setApplication] = useState<OwnerApplication | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [activeTab, setActiveTab] = useState("profile");
  const [pending, setPending] = useState(false);
  const [serverError, setServerError] = useState<unknown>(null);
  const toast = useToast();
  const tabs = [
    { id: "profile", label: "Profile details" },
    { id: "security", label: "Security" },
    ...(profile?.role === "requester" ? [{ id: "ownership", label: "Resource owner" }] : []),
  ];

  async function loadProfile() {
    setLoading(true);
    setLoadError(null);
    try {
      const [account, owner] = await Promise.all([
        api.get<AccountProfile>("/me"),
        api.get<{ application: OwnerApplication | null }>("/me/owner-application"),
      ]);
      setProfile(account);
      setApplication(owner.application);
    } catch (loadFailure) {
      setLoadError(loadFailure);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadProfile();
  }, []);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile) return;
    setPending(true);
    setServerError(null);
    try {
      const updated = await api.patch<AccountProfile>("/me", {
        full_name: profile.full_name,
        organization_name: profile.organization_name,
        phone: profile.phone,
        intended_use: profile.intended_use,
      });
      setProfile(updated);
      toast.show("Profile details saved.");
    } catch (saveError) {
      setServerError(saveError);
    } finally {
      setPending(false);
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const currentPassword = String(formData.get("current_password") ?? "");
    const newPassword = String(formData.get("new_password") ?? "");
    const confirmPassword = String(formData.get("confirm_password") ?? "");
    if (newPassword !== confirmPassword) {
      setServerError(new Error("New password and confirmation do not match."));
      return;
    }
    setPending(true);
    setServerError(null);
    try {
      await api.post("/me/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      form.reset();
      toast.show("Password changed successfully.");
    } catch (changeError) {
      setServerError(changeError);
    } finally {
      setPending(false);
    }
  }

  async function submitOwnerApplication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setPending(true);
    setServerError(null);
    try {
      const result = await api.post<OwnerApplication>("/owner-applications", {
        organization: String(formData.get("organization") ?? ""),
        role_in_organization: String(formData.get("role_in_organization") ?? ""),
        reason: String(formData.get("reason") ?? ""),
        resources_to_list: String(formData.get("resources_to_list") ?? ""),
      });
      setApplication(result);
      toast.show("Owner application submitted.");
    } catch (applicationError) {
      setServerError(applicationError);
    } finally {
      setPending(false);
    }
  }

  if (loading) return <div className="page-content"><div className="skeleton skeleton-block" role="status" aria-label="Loading profile" /></div>;
  if (loadError) return <main className="page-content"><Alert tone="danger" title="Profile could not be loaded">{errorText(loadError)}</Alert></main>;
  if (!profile) return <main className="page-content"><EmptyState>Your profile is not available.</EmptyState></main>;

  const completionItems = [
    { label: "Name", complete: Boolean(profile.full_name.trim()) },
    { label: "Organization", complete: Boolean(profile.organization_name?.trim()) },
    { label: "Discovery goal", complete: Boolean(profile.intended_use?.trim()) },
  ];
  const completedProfileItems = completionItems.filter((item) => item.complete).length;
  const profileCompletion = Math.round((completedProfileItems / completionItems.length) * 100);

  return (
    <div className="page-content">
      <PageHeading title="Your profile" description="Set the context behind your access and resource recommendations." />
      <section className="profile-overview" aria-label="Profile overview">
        <div className="profile-overview-identity">
          <span className="profile-avatar profile-avatar-large" aria-hidden="true">{profile.full_name.slice(0, 1).toUpperCase()}</span>
          <div>
            <p className="eyebrow">OPENVAULT ACCOUNT</p>
            <h2>{profile.full_name}</h2>
            <p>{roleLabels[profile.role]}{profile.organization_name && <> <span aria-hidden="true">·</span> {profile.organization_name}</>} <span aria-hidden="true">·</span> {profile.status}</p>
          </div>
        </div>
        <div className="profile-completion">
          <div className="profile-completion-heading"><span>Profile basics</span><strong>{completedProfileItems} / {completionItems.length}</strong></div>
          <progress value={profileCompletion} max="100" aria-label={`Profile ${profileCompletion}% complete`} />
          <ul>{completionItems.map((item) => <li className={item.complete ? "complete" : "incomplete"} key={item.label}><span aria-hidden="true">{item.complete ? "✓" : "○"}</span>{item.label}</li>)}</ul>
          <p>Adding a discovery goal improves the resource recommendations shown on your dashboard.</p>
        </div>
      </section>
      {serverError !== null && <Alert tone="danger" title="We couldn’t save your changes">{errorText(serverError)}</Alert>}
      <Tabs tabs={tabs} value={activeTab} onChange={setActiveTab} />
      {activeTab === "profile" && (
        <section className="profile-tab" role="tabpanel" id="panel-profile" aria-labelledby="tab-profile">
          <Card className="profile-card">
            <form className="profile-form" onSubmit={(event) => void saveProfile(event)}>
              <Input label="Full name" autoComplete="name" required maxLength={120} value={profile.full_name} onChange={(event) => setProfile({ ...profile, full_name: event.target.value })} />
              <Input label="Email address" type="email" value={profile.email ?? ""} readOnly helper="Email address cannot be changed in this prototype." />
              <Input label="Organization (optional)" autoComplete="organization" maxLength={200} value={profile.organization_name ?? ""} onChange={(event) => setProfile({ ...profile, organization_name: event.target.value || null })} />
              <Input label="Phone (optional)" type="tel" autoComplete="tel" maxLength={40} value={profile.phone ?? ""} onChange={(event) => setProfile({ ...profile, phone: event.target.value || null })} />
              <Textarea label="What do you want to use OpenVault for? (optional)" maxLength={2000} rows={4} value={profile.intended_use ?? ""} onChange={(event) => setProfile({ ...profile, intended_use: event.target.value || null })} />
              <div className="profile-actions"><Button type="submit" disabled={pending}>{pending ? "Saving…" : "Save profile"}</Button></div>
            </form>
          </Card>
        </section>
      )}
      {activeTab === "security" && (
        <section className="profile-tab" role="tabpanel" id="panel-security" aria-labelledby="tab-security">
          <Card className="profile-card profile-card-narrow">
            <h2>Change password</h2>
            <p className="muted">Enter your current password before choosing a new one.</p>
            <form className="profile-form" onSubmit={(event) => void changePassword(event)}>
              <Input label="Current password" name="current_password" type="password" autoComplete="current-password" required />
              <Input label="New password" name="new_password" type="password" autoComplete="new-password" minLength={10} required helper="At least 10 characters; cannot contain only digits." />
              <Input label="Confirm new password" name="confirm_password" type="password" autoComplete="new-password" minLength={10} required />
              <Button type="submit" disabled={pending}>{pending ? "Updating…" : "Change password"}</Button>
            </form>
          </Card>
        </section>
      )}
      {activeTab === "ownership" && profile.role === "requester" && (
        <section className="profile-tab" role="tabpanel" id="panel-ownership" aria-labelledby="tab-ownership">
          {application ? (
            <Card className="profile-card">
              <div className="card-title-row"><div><p className="eyebrow">OWNER APPLICATION</p><h2>Application status</h2></div><Badge tone={application.status === "approved" ? "success" : application.status === "rejected" ? "danger" : "warning"}>{application.status}</Badge></div>
              <dl className="request-details">
                <div><dt>Organization</dt><dd>{application.organization}</dd></div>
                <div><dt>Role</dt><dd>{application.role_in_organization}</dd></div>
                <div><dt>Submitted</dt><dd><time dateTime={application.created_at}>{new Date(application.created_at).toLocaleDateString()}</time></dd></div>
                <div><dt>Reason</dt><dd>{application.reason}</dd></div>
                <div><dt>Resources to list</dt><dd>{application.resources_to_list}</dd></div>
                {application.decision_reason && <div><dt>Decision note</dt><dd>{application.decision_reason}</dd></div>}
              </dl>
              {application.status === "pending" && <Alert tone="info">Your application is awaiting an institution administrator’s decision.</Alert>}
              {application.status === "rejected" && <Alert tone="warning">If your circumstances change, contact your institution administrator before submitting another application.</Alert>}
            </Card>
          ) : (
            <Card className="profile-card">
              <p className="eyebrow">RESOURCE OWNER ACCESS</p><h2>Apply to list and manage resources</h2>
              <p className="muted">Applications are reviewed by an institution administrator. Approval scopes management to your organization.</p>
              <form className="profile-form" onSubmit={(event) => void submitOwnerApplication(event)}>
                <Input label="Organization" name="organization" required maxLength={200} defaultValue={profile.organization_name ?? ""} />
                <Input label="Your role in the organization" name="role_in_organization" required maxLength={160} />
                <Textarea label="Why do you need resource owner access?" name="reason" required maxLength={2000} rows={3} />
                <Textarea label="What resources would you like to list?" name="resources_to_list" required maxLength={2000} rows={3} />
                <Button type="submit" disabled={pending}>{pending ? "Submitting…" : "Submit application"}</Button>
              </form>
            </Card>
          )}
        </section>
      )}
      <Toast message={toast.message} onDismiss={toast.dismiss} />
    </div>
  );
}

export function PrivacyPage() {
  return (
    <main className="legal-page">
      <Link className="brand" to="/">openvault<span aria-hidden="true">.</span></Link>
      <PageHeading title="Privacy and prototype limitations" description="A clear explanation of this prototype’s scope." />
      <Card><h2>Use of information</h2><p>OpenVault processes account, profile, booking, training and audit information to support the resource coordination workflows configured by your institution. Access and retention are subject to institutional policies.</p><h2>Prototype limitations</h2><p>This prototype does not replace institutional safety procedures, legal agreements, or local approval processes. Demo records are fictional sample data and must not be interpreted as live institutional statistics.</p></Card>
      <Link className="back-link" to="/">← Return to OpenVault</Link>
    </main>
  );
}

export function TermsPage() {
  return (
    <main className="legal-page">
      <Link className="brand" to="/">openvault<span aria-hidden="true">.</span></Link>
      <PageHeading title="Terms of use" description="Use this prototype in accordance with your institution’s policies." />
      <Card><h2>Responsible resource use</h2><p>Follow the resource owner’s instructions, complete required training and use equipment only for an approved purpose. An application or request does not guarantee access; a manager must approve each request.</p><h2>Condition and safety</h2><p>Record equipment condition honestly at handover and follow all local safety guidance. Report problems promptly through the institution’s established channels.</p></Card>
      <Link className="back-link" to="/">← Return to OpenVault</Link>
    </main>
  );
}
