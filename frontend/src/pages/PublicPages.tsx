import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { JudgeRole, PublicSummary, Role } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { PageHeading, StatusBadge } from "../components/PageHeading";
import { ErrorState, Loading } from "../components/Feedback";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  Stepper,
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
  return (
    <div className="public-page">
      <header className="public-header">
        <Link className="brand" to="/" aria-label="OpenVault home">openvault<span aria-hidden="true">.</span></Link>
        <nav className="public-nav" aria-label="Public navigation">
          <a href="#how-it-works">How it works</a>
          <a href="#features">Features</a>
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
        <section className="hero-section">
          <div className="hero-copy">
            <p className="eyebrow"><span className="eyebrow-dot" /> SHARED LAB RESOURCES, MADE ACCESSIBLE</p>
            <h1>Make more of the equipment you already have.</h1>
            <p className="hero-description">
              OpenVault helps institutions share equipment and spaces through clear eligibility,
              accountable decisions and safer, fairer bookings.
            </p>
            <div className="hero-actions">
              <Link className="button button-primary button-large" to={browsePath}>Browse resources <span aria-hidden="true">→</span></Link>
              {!user && <Link className="text-link" to="/signup">Create an account</Link>}
            </div>
            <p className="hero-footnote">For learning, research and project work. Availability and access are set by each institution.</p>
          </div>
          <div className="hero-visual" aria-label="Illustration of shared equipment and a booking schedule" role="img">
            <div className="visual-orbit orbit-one" />
            <div className="visual-orbit orbit-two" />
            <div className="visual-card visual-card-main">
              <div className="visual-card-top"><span className="visual-icon">O</span><span className="visual-status"><i /> READY TO REQUEST</span></div>
              <span className="visual-label">RESOURCE CATALOG</span>
              <strong>Tools for your<br />next big idea.</strong>
              <div className="visual-card-bottom"><span>Clear requirements</span><span aria-hidden="true">↗</span></div>
            </div>
            <div className="visual-card visual-card-note"><span className="note-mark">✓</span><div><strong>Every step accounted for</strong><small>From request to return</small></div></div>
            <span className="visual-spark spark-one" aria-hidden="true">✳</span>
            <span className="visual-spark spark-two" aria-hidden="true">✳</span>
          </div>
        </section>

        <section className="problem-section section-wrap">
          <div className="section-intro">
            <p className="eyebrow">THE OPPORTUNITY</p>
            <h2>Good resources shouldn’t sit idle.</h2>
            <p>Sharing works when people know what’s available, what’s expected, and how decisions are made.</p>
          </div>
          <div className="problem-grid">
            {[
              ["01", "Idle equipment", "Useful tools and rooms can remain underused when discovery and booking are difficult."],
              ["02", "Trust and safety", "Clear eligibility, training and condition records set expectations before a session begins."],
              ["03", "Fair access", "A consistent queue and an accountable human decision help make access easier to understand."],
            ].map(([number, title, description]) => (
              <Card className="problem-card" key={number}>
                <span className="section-number">{number}</span>
                <h3>{title}</h3>
                <p>{description}</p>
              </Card>
            ))}
          </div>
        </section>

        <BrowseByCity userIsSignedIn={Boolean(user)} />

        <section className="how-section" id="how-it-works">
          <div className="section-wrap">
            <div className="section-intro section-intro-centered">
              <p className="eyebrow">A CLEAR PATH FROM NEED TO USE</p>
              <h2>Five simple steps.</h2>
              <p>People stay informed at every step. Managers stay in control of approvals.</p>
            </div>
            <Stepper steps={[
              { title: "Discover", description: "Search the catalog for equipment and spaces." },
              { title: "Check", description: "Review access, training and supervision requirements." },
              { title: "Request", description: "Choose an available time and submit your purpose." },
              { title: "Decide", description: "A resource manager reviews and records the decision." },
              { title: "Return", description: "Complete the condition checklist at handover." },
            ]} />
          </div>
        </section>

        <section className="features-section section-wrap" id="features">
          <div className="section-intro">
            <p className="eyebrow">BUILT FOR SHARED ACCESS</p>
            <h2>Clear expectations. Better stewardship.</h2>
          </div>
          <div className="feature-columns">
            <Card className="feature-card">
              <Badge tone="info">FOR REQUESTERS</Badge>
              <h3>Know what you need before you book.</h3>
              <ul className="feature-list">
                <li><span>✓</span><div><strong>Eligibility checks</strong><p>See training, supervision and policy requirements up front.</p></div></li>
                <li><span>✓</span><div><strong>Transparent requests</strong><p>Follow decisions and any next steps in one place.</p></div></li>
                <li><span>✓</span><div><strong>Condition records</strong><p>Record the state of equipment during check-in and return.</p></div></li>
              </ul>
            </Card>
            <Card className="feature-card feature-card-owner">
              <Badge tone="success">FOR RESOURCE OWNERS</Badge>
              <h3>Share access without losing oversight.</h3>
              <ul className="feature-list">
                <li><span>✓</span><div><strong>Fair allocation</strong><p>Review competing eligible requests with understandable inputs.</p></div></li>
                <li><span>✓</span><div><strong>Policy versions</strong><p>Keep existing session conditions intact as resource rules evolve.</p></div></li>
                <li><span>✓</span><div><strong>Audit trail</strong><p>Keep decisions and changes attributable and reviewable.</p></div></li>
              </ul>
            </Card>
          </div>
        </section>

        <section className="closing-cta">
          <div><p className="eyebrow">START WITH WHAT’S AVAILABLE</p><h2>Find the right resource for your work.</h2></div>
          <Link className="button button-light button-large" to={browsePath}>Browse resources <span aria-hidden="true">→</span></Link>
        </section>
      </main>
      <footer className="public-footer">
        <Link className="brand" to="/">openvault<span aria-hidden="true">.</span></Link>
        <p>OpenVault is a prototype for institutional resource coordination. Availability, eligibility and approvals depend on the institution. It does not replace local safety procedures or institutional policy.</p>
        <Link to="/privacy">Privacy and limitations</Link>
        <span>© OpenVault</span>
      </footer>
    </div>
  );
}

function BrowseByCity({ userIsSignedIn }: { userIsSignedIn: boolean }) {
  const [cities, setCities] = useState<PublicSummary["cities"]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void api.get<PublicSummary>("/public/summary").then(
      (result) => active && setCities(result.cities),
      (loadError: unknown) => active && setError(loadError),
    ).finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="browse-city-section section-wrap" aria-labelledby="browse-city-title">
      <div className="section-intro">
        <p className="eyebrow">EXPLORE THE CATALOG</p>
        <h2 id="browse-city-title">Browse by city.</h2>
        <p>See the resources and organizations listed for each city.</p>
      </div>
      {error !== null ? (
        <ErrorState error={error} />
      ) : loading ? (
        <Loading label="Loading city summary…" />
      ) : cities.length === 0 ? (
        <p className="muted">No city information is currently available.</p>
      ) : (
        <div className="browse-city-grid">
          {cities.map((entry) => (
            <Link
              className="browse-city-card"
              key={entry.city}
              to={userIsSignedIn
                ? `/resources?city=${encodeURIComponent(entry.city)}`
                : `/login?next=${encodeURIComponent(`/resources?city=${entry.city}`)}`}
            >
              <span aria-hidden="true">⌖</span>
              <strong>{entry.city}</strong>
              <small>
                {entry.resource_count} {entry.resource_count === 1 ? "resource" : "resources"} ·{" "}
                {entry.organization_count} {entry.organization_count === 1 ? "organization" : "organizations"}
              </small>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

export function LoginPage() {
  const { judgeLoginAvailable, signIn, signInJudge } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const nextPath = new URLSearchParams(location.search).get("next");
  const safeNextPath = nextPath?.startsWith("/") && !nextPath.startsWith("//") ? nextPath : "/resources";

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

  async function quickLogin(role: JudgeRole) {
    setPending(true);
    setError(null);
    try {
      await signInJudge(role);
      navigate("/dashboard", { replace: true });
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
          {judgeLoginAvailable && (
            <section className="judge-access-panel" aria-labelledby="judge-access-title">
              <div>
                <p className="eyebrow">EVALUATION ACCESS</p>
                <h3 id="judge-access-title">Judge access</h3>
                <p className="muted">Open a fictional sample account with one click.</p>
              </div>
              <div className="judge-access-options">
                {([
                  ["requester", "Requester", "Find resources and submit a booking request."],
                  ["manager", "Lab manager", "Review requests and manage resource access."],
                  ["auditor", "Auditor", "Explore sample activity and the audit trail."],
                ] as const).map(([role, label, description]) => (
                  <Button
                    className="judge-access-button"
                    key={role}
                    type="button"
                    variant="secondary"
                    disabled={pending}
                    onClick={() => void quickLogin(role)}
                  >
                    <span className="judge-access-button-copy">
                      <strong>{label}</strong>
                      <small>{description}</small>
                    </span>
                    <span aria-hidden="true">→</span>
                  </Button>
                ))}
              </div>
            </section>
          )}
          {error !== null && <Alert tone="danger" title="We couldn’t sign you in">{errorText(error)}</Alert>}
          <form onSubmit={(event) => void submit(event)} noValidate>
            <Input label="Email address" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
            <div className="password-field">
              <Input label="Password" type={showPassword ? "text" : "password"} autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
              <button type="button" className="password-toggle" onClick={() => setShowPassword((value) => !value)} aria-pressed={showPassword}>{showPassword ? "Hide" : "Show"}</button>
            </div>
            <div className="auth-links"><Link to="/login?forgot=1">Forgot password?</Link><Link to="/signup">Sign up</Link></div>
            {new URLSearchParams(location.search).has("forgot") && (
              <Alert className="forgot-note" title="Password reset isn’t available in this prototype">
                Please contact your institution administrator for help accessing your account.
              </Alert>
            )}
            <Button className="w-full button-large" type="submit" disabled={pending}>{pending ? "Signing in…" : "Sign in"}</Button>
          </form>

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

  return (
    <div className="page-content">
      <PageHeading title="Your profile" description="Manage your account details, security and resource owner application." />
      {serverError !== null && <Alert tone="danger" title="We couldn’t save your changes">{errorText(serverError)}</Alert>}
      <Tabs tabs={tabs} value={activeTab} onChange={setActiveTab} />
      {activeTab === "profile" && (
        <section className="profile-tab" role="tabpanel" id="panel-profile" aria-labelledby="tab-profile">
          <Card className="profile-card">
            <div className="profile-intro"><span className="profile-avatar" aria-hidden="true">{profile.full_name.slice(0, 1).toUpperCase()}</span><div><h2>{profile.full_name}</h2><p>{roleLabels[profile.role]} <span aria-hidden="true">·</span> {profile.status}</p></div></div>
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
              <div className="card-title-row"><div><p className="eyebrow">OWNER APPLICATION</p><h2>Application status</h2></div><StatusBadge value={application.status} /></div>
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
