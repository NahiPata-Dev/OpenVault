import { Component, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  BrowserRouter,
  Link,
  Navigate,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { api } from "./api/client";
import type { JudgeRole, Role, User } from "./api/types";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { ErrorState } from "./components/Feedback";
import { BookingAssistant } from "./components/BookingAssistant";
import { PageHeading, StatusBadge } from "./components/PageHeading";
import { Alert, Badge, Button, Card, EmptyState, StatCard } from "./components/UI";
import { formatIST } from "./lib/format";
import {
  LandingPage,
  LoginPage,
  PrivacyPage,
  ProfilePage,
  SignupPage,
  TermsPage,
} from "./pages/PublicPages";
import { ResourceDetailPage, ResourcesPage } from "./pages/ResourcesPage";
import { BookingDetailPage, ContractPage, MyBookingsPage, RequestsPage } from "./pages/RequestsPage";
import {
  IncidentDetailPage,
  IncidentListPage,
  ManagerQueuePage,
  ManagerSessionsPage,
  TrainingPage,
} from "./pages/ManagerPages";
import { ResourceManagementPage } from "./pages/ResourceManagementPage";
import {
  AdminAuditExplorerPage,
  AdminOwnerApplicationsPage,
  AdminPage,
  AdminUsersPage,
  AuditTimelinePage,
  ResourceMemoryPage,
} from "./pages/AuditMemoryPages";

const roleLabels: Record<Role, string> = {
  requester: "Requester",
  lab_manager: "Lab manager",
  institution_admin: "Institution admin",
  auditor: "Judge auditor",
};

interface NotificationItem {
  id: string;
  type: string;
  related_entity_type: string;
  related_entity_id: string;
  read_at: string | null;
  created_at: string;
  is_demo?: boolean;
}

function NotificationBell({ role }: { role: Role }) {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const unreadCount = items.filter((item) => item.read_at === null).length;

  useEffect(() => {
    let active = true;
    void api.get<{ items: NotificationItem[] }>("/notifications").then(
      (result) => active && setItems(result.items),
      (loadError: unknown) => active && setError(loadError),
    ).finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  async function markRead(item: NotificationItem) {
    if (item.read_at || item.type === "overdue_return") return;
    try {
      await api.post(`/notifications/${item.id}/read`);
      setItems((current) => current.map((row) => row.id === item.id ? { ...row, read_at: new Date().toISOString() } : row));
    } catch (markError) {
      setError(markError);
    }
  }

  const destination = (item: NotificationItem) => {
    if (item.related_entity_type === "resource") return `/resources/${item.related_entity_id}`;
    if (item.related_entity_type === "incident" && role === "lab_manager") return `/manager/incidents/${item.related_entity_id}`;
    if (item.related_entity_type === "booking") return role === "requester" ? "/requests" : "/manager/requests";
    return role === "requester" ? "/requests" : "/manager/requests";
  };

  return (
    <details className="notification-menu">
      <summary aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ""}`}>
        <svg className="bell-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="notification-label">Notifications</span>
        {unreadCount > 0 && <span className="notification-count">{unreadCount > 9 ? "9+" : unreadCount}</span>}
      </summary>
      <div className="notification-panel">
        <div className="notification-panel-heading"><h2>Notifications</h2><span>{unreadCount} unread</span></div>
        {error !== null && <ErrorState error={error} />}
        {loading ? <p className="helper">Loading notifications…</p> : items.length === 0 && !error ? (
          <EmptyState title="You’re all caught up">New decisions and booking reminders will appear here.</EmptyState>
        ) : (
          <ul className="notification-list">
            {items.slice(0, 8).map((item) => (
              <li key={item.id} className={item.read_at ? "" : "notification-unread"}>
                <Link to={destination(item)} onClick={() => void markRead(item)}>
                  <span className="notification-title">{item.type.replaceAll("_", " ")}</span>
                  <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time>
                  {item.is_demo && <Badge>Sample data</Badge>}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </details>
  );
}

function breadcrumbLabel(segment: string): string {
  const labels: Record<string, string> = {
    resources: "Resources",
    requests: "My requests",
    bookings: "My bookings",
    contracts: "Access Contract",
    manager: "Manager workspace",
    incidents: "Incidents",
    training: "Training",
    audit: "Audit timeline",
    admin: "Admin",
    profile: "Profile",
    memory: "Resource Memory",
  };
  return labels[segment] ?? segment.replaceAll("-", " ");
}

function Breadcrumbs() {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);
  const crumbs = useMemo(() => segments.map((segment, index) => ({
    label: breadcrumbLabel(segment),
    path: `/${segments.slice(0, index + 1).join("/")}`,
  })), [segments.join("/")]);
  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      <Link to="/resources">Workspace</Link>
      {crumbs.map((crumb, index) => (
        <span key={crumb.path}>
          <span className="breadcrumb-divider" aria-hidden="true">/</span>
          {index === crumbs.length - 1 ? <span aria-current="page">{crumb.label}</span> : <Link to={crumb.path}>{crumb.label}</Link>}
        </span>
      ))}
    </nav>
  );
}

function AppHeader({ user }: { user: User }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const { judgeMode, signOut, switchJudgeRole } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const moreMenuRef = useRef<HTMLDetailsElement>(null);
  const [logoutError, setLogoutError] = useState<unknown>(null);
  const [switchError, setSwitchError] = useState<unknown>(null);
  const [switchPending, setSwitchPending] = useState(false);
  const navigationByRole: Record<Role, { primary: { path: string; label: string }[]; more: { path: string; label: string }[] }> = {
    requester: {
      primary: [
        { path: "/dashboard", label: "Home" },
        { path: "/resources", label: "Find a resource" },
        { path: "/bookings", label: "My bookings" },
        { path: "/requests", label: "My requests" },
      ],
      more: [{ path: "/audit", label: "Audit timeline" }],
    },
    lab_manager: {
      primary: [
        { path: "/dashboard", label: "Home" },
        { path: "/manager/requests", label: "Review requests" },
        { path: "/manager/resources", label: "My resources" },
        { path: "/manager/sessions", label: "Today's sessions" },
      ],
      more: [
        { path: "/manager/training", label: "Training sign-off" },
        { path: "/manager/incidents", label: "Incidents" },
        { path: "/resources", label: "Browse catalog" },
        { path: "/audit", label: "Audit timeline" },
      ],
    },
    institution_admin: {
      primary: [
        { path: "/dashboard", label: "Home" },
        { path: "/admin/owner-applications", label: "Owner applications" },
        { path: "/admin/users", label: "Users" },
        { path: "/admin/audit", label: "Audit" },
      ],
      more: [
        { path: "/admin", label: "Demo data reset" },
        { path: "/audit", label: "Resource audit timeline" },
        { path: "/resources", label: "Browse catalog" },
      ],
    },
    auditor: {
      primary: [
        { path: "/dashboard", label: "Home" },
        { path: "/resources", label: "Resources" },
        { path: "/audit", label: "Audit" },
      ],
      more: [{ path: "/profile", label: "Profile and settings" }],
    },
  };
  const { primary, more } = navigationByRole[user.role];
  const linkClassName = ({ isActive }: { isActive: boolean }) =>
    `app-nav-link ${isActive ? "active" : ""}`;

  async function logout() {
    setLogoutError(null);
    try {
      await signOut();
      navigate("/login", { replace: true });
    } catch (error) {
      setLogoutError(error);
    }
  }

  async function switchRole(role: JudgeRole) {
    setSwitchPending(true);
    setSwitchError(null);
    try {
      await switchJudgeRole(role);
      navigate("/dashboard", { replace: true });
    } catch (error) {
      setSwitchError(error);
    } finally {
      setSwitchPending(false);
    }
  }

  useEffect(() => {
    setMenuOpen(false);
    if (moreMenuRef.current) moreMenuRef.current.open = false;
  }, [location.pathname]);

  return (
    <>
      <header className="app-header">
        <Link className="brand" to="/resources" aria-label="OpenVault workspace">openvault<span aria-hidden="true">.</span></Link>
        <button className="mobile-menu-toggle" type="button" aria-expanded={menuOpen} aria-controls="primary-navigation" onClick={() => setMenuOpen((open) => !open)}>
          <span aria-hidden="true">{menuOpen ? "×" : "☰"}</span><span className="sr-only">{menuOpen ? "Close menu" : "Open menu"}</span>
        </button>
        <nav className={`app-nav ${menuOpen ? "app-nav-open" : ""}`} id="primary-navigation" aria-label="Main navigation">
          {primary.map((item) => (
            <NavLink key={item.path} to={item.path} end={item.path === "/resources" || item.path === "/dashboard"} className={linkClassName}>
              {item.label}
            </NavLink>
          ))}
          {more.length > 0 && (
            <details className="more-menu" ref={moreMenuRef}>
              <summary>More</summary>
              <div className="more-menu-panel">
                {more.map((item) => (
                  <NavLink key={item.path} to={item.path} className={linkClassName}>
                    {item.label}
                  </NavLink>
                ))}
              </div>
            </details>
          )}
        </nav>
        <div className="header-actions">
          <NotificationBell role={user.role} />
          {judgeMode && (
            <details className="judge-switch-menu">
              <summary>Switch role</summary>
              <div className="judge-switch-panel">
                <strong>Judge role</strong>
                {([
                  ["requester", "Requester"],
                  ["manager", "Lab manager"],
                  ["auditor", "Auditor"],
                ] as const).map(([role, label]) => (
                  <Button
                    key={role}
                    type="button"
                    variant="quiet"
                    disabled={switchPending}
                    onClick={() => void switchRole(role)}
                  >
                    {label}
                  </Button>
                ))}
                {switchError !== null && <ErrorState error={switchError} />}
              </div>
            </details>
          )}
          <details className="user-menu">
            <summary><span className="avatar" aria-hidden="true">{user.display_name.slice(0, 1).toUpperCase()}</span><span className="user-menu-name">{user.display_name}</span><span aria-hidden="true">⌄</span></summary>
            <div className="user-menu-panel">
              <strong>{user.display_name}</strong><span>{roleLabels[user.role]}</span>
              <Link to="/profile">Profile and settings</Link>
              <Button type="button" variant="quiet" onClick={() => void logout()}>Sign out</Button>
            </div>
          </details>
        </div>
      </header>
      <div className="workspace-subheader"><Breadcrumbs /></div>
      {logoutError !== null && <div className="page-content"><ErrorState error={logoutError} /></div>}
    </>
  );
}

interface JudgeGuideRequest {
  request: { status: string };
  decision?: { outcome: string } | null;
  booking?: { status: string } | null;
  access_contract?: { status: string } | null;
}

interface JudgeGuideFacts {
  resources: number;
  requests: JudgeGuideRequest[];
  managerRequests: { request: { status: string } }[];
  auditActions: string[];
  openIncidents: number;
}

function JudgeGuide({ role }: { role: Role }) {
  const navigate = useNavigate();
  const [facts, setFacts] = useState<JudgeGuideFacts | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setError(null);
    const load = async () => {
      try {
        const [resources, audit] = await Promise.all([
          api.get<{ total: number }>("/resources"),
          api.get<{ items: { action: string }[] }>("/audit"),
        ]);
        let requests: JudgeGuideRequest[] = [];
        let managerRequests: JudgeGuideFacts["managerRequests"] = [];
        let openIncidents = 0;
        if (role === "requester") {
          const history = await api.get<{ items: JudgeGuideRequest[] }>("/requests/mine");
          requests = history.items;
        } else if (role === "lab_manager") {
          const [queue, dashboard] = await Promise.all([
            api.get<{ items: JudgeGuideFacts["managerRequests"] }>("/manager/requests"),
            api.get<{ summary: { open_incidents: number } }>("/dashboard/manager"),
          ]);
          managerRequests = queue.items;
          openIncidents = dashboard.summary.open_incidents;
        }
        if (active) {
          setFacts({
            resources: resources.total,
            requests,
            managerRequests,
            auditActions: audit.items.map((item) => item.action),
            openIncidents,
          });
        }
      } catch (loadError) {
        if (active) setError(loadError);
      }
    };
    void load();
    return () => { active = false; };
  }, [role, reloadKey]);

  const actions = facts?.auditActions ?? [];
  const requestRecords = facts?.requests ?? [];
  const managerRecords = facts?.managerRequests ?? [];
  const hasRequests = requestRecords.length > 0
    || managerRecords.length > 0
    || actions.some((action) => action.startsWith("request."));
  const hasBooking = requestRecords.some((item) => item.booking !== null && item.booking !== undefined)
    || actions.some((action) => action === "booking.confirmed");
  const checkedIn = requestRecords.some((item) =>
    ["CHECKED_IN", "CLOSED"].includes(item.booking?.status ?? ""),
  ) || actions.some((action) => ["booking.checked_in", "booking.late_checked_in"].includes(action));
  const checkedOut = requestRecords.some((item) => item.booking?.status === "CLOSED")
    || actions.some((action) => ["booking.checked_out", "booking.closed"].includes(action));
  const reportedIncident = requestRecords.some((item) => item.request.status === "INCIDENT_REVIEW")
    || (facts?.openIncidents ?? 0) > 0
    || actions.some((action) => action.startsWith("incident."));
  const resolvedIncident = actions.some((action) =>
    ["incident.resolved", "incident.dismissed"].includes(action),
  );
  const completed = [
    (facts?.resources ?? 0) > 0,
    false,
    hasRequests,
    requestRecords.some((item) => item.decision?.outcome === "approved") || hasBooking,
    requestRecords.some((item) => item.access_contract !== null && item.access_contract !== undefined)
      || actions.some((action) => action === "booking.confirmed"),
    checkedIn,
    checkedOut,
    reportedIncident,
    resolvedIncident,
    actions.length > 0,
  ];
  const steps = [
    { title: "Find a resource", instruction: "Browse the sample catalog.", path: "/resources" },
    { title: "Check requirements", instruction: "Review training, rules, and availability.", path: "/resources" },
    {
      title: role === "requester" ? "Submit a request" : "Review requests",
      instruction: role === "requester" ? "Choose a resource and submit your purpose." : "Open the manager queue to review requests.",
      path: role === "requester" ? "/resources" : role === "lab_manager" ? "/manager/requests" : "/audit",
    },
    {
      title: role === "lab_manager" ? "Record a decision" : "Review the decision",
      instruction: "An authorized manager records the outcome.",
      path: role === "lab_manager" ? "/manager/requests" : role === "requester" ? "/requests" : "/audit",
    },
    {
      title: "Review the Access Contract",
      instruction: "Read the session conditions for a confirmed booking.",
      path: role === "requester" ? "/requests" : role === "lab_manager" ? "/manager/sessions" : "/audit",
    },
    {
      title: "Check in",
      instruction: "Complete the condition checklist at arrival.",
      path: role === "requester" ? "/bookings" : role === "lab_manager" ? "/manager/sessions" : "/audit",
    },
    {
      title: "Check out",
      instruction: "Record the condition and return shared items.",
      path: role === "requester" ? "/bookings" : role === "lab_manager" ? "/manager/sessions" : "/audit",
    },
    {
      title: "Report an incident",
      instruction: "Record issues for human review without assigning blame.",
      path: role === "lab_manager" ? "/manager/incidents" : role === "requester" ? "/bookings" : "/audit",
    },
    {
      title: "Resolve an incident",
      instruction: "Review and record the manager's resolution.",
      path: role === "lab_manager" ? "/manager/incidents" : role === "requester" ? "/requests" : "/audit",
    },
    { title: "Review the audit trail", instruction: "Inspect the recorded lifecycle events.", path: "/audit" },
  ];

  return (
    <details className="judge-guide">
      <summary><span>Judge guide</span><small>10-step request-to-return walkthrough</small></summary>
      <ol className="judge-guide-steps">
        {steps.map((step, index) => (
          <li key={step.title} className={completed[index] ? "judge-guide-complete" : ""}>
            <span className="judge-guide-check" aria-label={completed[index] ? "Completed from saved records" : "Not yet recorded"}>
              {completed[index] ? "✓" : String(index + 1)}
            </span>
            <div className="judge-guide-copy">
              <strong>{step.title}</strong>
              <p>{step.instruction}</p>
            </div>
            <Button type="button" variant="secondary" onClick={() => navigate(step.path)}>
              Open
            </Button>
          </li>
        ))}
      </ol>
      {error !== null && (
        <div className="judge-guide-error">
          <ErrorState error={error} />
          <Button type="button" variant="secondary" onClick={() => setReloadKey((key) => key + 1)}>
            Retry guide data
          </Button>
        </div>
      )}
      <p className="helper">Completion ticks reflect saved requests, bookings, incidents, and audit events. The app does not record page views.</p>
    </details>
  );
}

interface DashboardItem {
  id: string;
  type: string;
  title: string;
  at: string | null;
  status: string;
}

interface DashboardData {
  summary: Record<string, number>;
  next_items: DashboardItem[];
}

interface DashboardRequestRecord {
  request: {
    id: string;
    status: string;
    purpose: string;
    resource_id: string;
    start_at: string;
    end_at: string;
    is_demo: boolean;
  };
  booking: {
    id: string;
    status: string;
    start_at: string;
    end_at: string;
  } | null;
}

interface AdminDashboardState {
  applications: number;
  pendingApplications: number;
  users: number;
}

interface AuditorResourceSummary {
  total: number;
  active: number;
  needsReview: number;
}

interface DashboardAction {
  title: string;
  description: string;
  path?: string;
  assistant?: boolean;
}

const TIP_TOUR_KEY = "openvault.tip-tour.dismissed.v1";

function TipTour({ role }: { role: Role }) {
  const [step, setStep] = useState(0);
  const [dismissed, setDismissed] = useState<boolean | null>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const tips = [
    {
      title: "Start from your home page",
      text: "Use the three large shortcuts to jump to the task you need most.",
    },
    {
      title: "Your next step is based on your account",
      text: "The dashboard uses your own requests, bookings, training, or manager queue to suggest what to do next.",
    },
    {
      title: role === "requester" ? "Get help when you need it" : "Find the rest under More",
      text: role === "requester"
        ? "The booking assistant can find resources and prepare a request. A person reviews every request."
        : "Less-used pages stay available in the More menu, so the main navigation stays focused.",
    },
  ];

  useEffect(() => {
    setDismissed(window.localStorage.getItem(TIP_TOUR_KEY) === "true");
  }, []);

  useEffect(() => {
    if (dismissed === false) {
      dialogRef.current?.querySelector<HTMLButtonElement>(".tip-tour-actions button:last-child")?.focus();
    }
  }, [dismissed, step]);

  function dismiss() {
    window.localStorage.setItem(TIP_TOUR_KEY, "true");
    setDismissed(true);
  }

  if (dismissed !== false) return null;
  const tip = tips[step];
  return (
    <div className="tip-tour-backdrop">
      <section
        className="tip-tour"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tip-tour-title"
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            dismiss();
            return;
          }
          if (event.key !== "Tab") return;
          const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"));
          const first = buttons[0];
          const last = buttons[buttons.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last?.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first?.focus();
          }
        }}
      >
        <p className="eyebrow">QUICK TOUR · {step + 1} OF {tips.length}</p>
        <h2 id="tip-tour-title">{tip.title}</h2>
        <p>{tip.text}</p>
        <div className="tip-tour-actions">
          <button className="button button-quiet" type="button" onClick={dismiss}>Skip tour</button>
          <button
            className="button button-primary"
            type="button"
            onClick={() => step === tips.length - 1 ? dismiss() : setStep((current) => current + 1)}
          >
            {step === tips.length - 1 ? "Finish" : "Next"}
          </button>
        </div>
      </section>
    </div>
  );
}

function DashboardPage({ user }: { user: User }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [requests, setRequests] = useState<DashboardRequestRecord[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [adminData, setAdminData] = useState<AdminDashboardState | null>(null);
  const [auditorResources, setAuditorResources] = useState<AuditorResourceSummary | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [loadVersion, setLoadVersion] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    const loads = user.role === "requester"
      ? Promise.all([
          api.get<DashboardData>("/dashboard/requester"),
          api.get<{ items: DashboardRequestRecord[] }>("/requests/mine"),
          api.get<{ items: NotificationItem[] }>("/notifications"),
        ]).then(([dashboard, history, notificationList]) => {
          if (!active) return;
          setData(dashboard);
          setRequests(history.items);
          setNotifications(notificationList.items);
        })
      : user.role === "lab_manager"
        ? api.get<DashboardData>("/dashboard/manager").then((dashboard) => active && setData(dashboard))
        : user.role === "institution_admin"
          ? Promise.all([
              api.get<{ status: string }[]>("/admin/owner-applications"),
              api.get<unknown[]>("/admin/users"),
            ]).then(([applications, users]) => active && setAdminData({
              applications: applications.length,
              pendingApplications: applications.filter((application) => application.status === "pending").length,
              users: users.length,
            }))
          : api.get<{
              total: number;
              items: { status: string; readiness: { ready: boolean } }[];
            }>("/resources").then((resources) => active && setAuditorResources({
              total: resources.total,
              active: resources.items.filter((resource) => resource.status === "active").length,
              needsReview: resources.items.filter((resource) => !resource.readiness.ready).length,
            }));
    void loads.catch((loadError: unknown) => active && setError(loadError))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [user.role, loadVersion]);
  const upcomingBookings = requests
    .filter((item) => item.booking && ["CONFIRMED", "CHECKED_IN", "NO_SHOW"].includes(item.booking.status) && new Date(item.booking.end_at).getTime() >= Date.now())
    .sort((a, b) => new Date(a.booking!.start_at).getTime() - new Date(b.booking!.start_at).getTime())
    .slice(0, 5);
  const pendingRequests = requests
    .filter((item) => ["PENDING_REVIEW", "WAITLISTED"].includes(item.request.status))
    .sort((a, b) => new Date(a.request.start_at).getTime() - new Date(b.request.start_at).getTime())
    .slice(0, 5);
  const expiringTraining = data?.next_items.filter((item) => item.type === "expiring_training") ?? [];
  const requesterNext = pendingRequests[0]
    ? {
        title: "A request is waiting for review",
        detail: `${pendingRequests[0].request.status === "WAITLISTED" ? "Waitlisted" : "Pending"} · ${formatIST(pendingRequests[0].request.start_at)}`,
        path: "/requests",
        label: "View my requests",
      }
    : upcomingBookings[0]?.booking
      ? {
          title: "Get ready for your next booking",
          detail: formatIST(upcomingBookings[0].booking.start_at),
          path: "/bookings",
          label: "View my bookings",
        }
      : (data?.summary.expiring_training ?? 0) > 0
        ? {
            title: "Training expires soon",
            detail: `${data?.summary.expiring_training} training ${data?.summary.expiring_training === 1 ? "record needs" : "records need"} attention.`,
            path: "/resources",
            label: "Find a resource",
          }
        : {
            title: "Find equipment for your next project",
            detail: "Browse the catalog to compare access rules and requirements.",
            path: "/resources",
            label: "Browse resources",
          };
  const managerNext = (data?.summary.pending_requests ?? 0) > 0
    ? {
        title: "Requests need a decision",
        detail: `${data?.summary.pending_requests} pending or waitlisted request${data?.summary.pending_requests === 1 ? "" : "s"} in your queue.`,
        path: "/manager/requests",
        label: "Review requests",
      }
    : (data?.summary.upcoming_bookings ?? 0) > 0
      ? {
          title: "Prepare for today's sessions",
          detail: `${data?.summary.upcoming_bookings} upcoming session${data?.summary.upcoming_bookings === 1 ? "" : "s"} in your schedule.`,
          path: "/manager/sessions",
          label: "View sessions",
        }
      : (data?.summary.open_incidents ?? 0) > 0
        ? {
            title: "An incident needs follow-up",
            detail: `${data?.summary.open_incidents} open incident${data?.summary.open_incidents === 1 ? "" : "s"} in your resources.`,
            path: "/manager/incidents",
            label: "Review incidents",
          }
        : {
            title: "Your queue is clear",
            detail: "Review your resources and keep their details up to date.",
            path: "/manager/resources",
            label: "View my resources",
          };

  const actionsByRole: Record<Role, DashboardAction[]> = {
    requester: [
      { title: "Find a resource", description: "Search equipment and spaces by city, type, or need.", path: "/resources" },
      { title: "My bookings", description: "See approved sessions and access conditions.", path: "/bookings" },
      { title: "Ask the assistant", description: "Find options, check requirements, or prepare a request." , assistant: true },
    ],
    lab_manager: [
      { title: "Review requests", description: "Check eligibility and record your decision.", path: "/manager/requests" },
      { title: "My resources", description: "Update resources and access requirements.", path: "/manager/resources" },
      { title: "Today's sessions", description: "See upcoming sessions in your organization.", path: "/manager/sessions" },
    ],
    institution_admin: [
      { title: "Owner applications", description: "Review applications for resource-owner access.", path: "/admin/owner-applications" },
      { title: "Users", description: "Review account roles and status.", path: "/admin/users" },
      { title: "Audit", description: "Explore recorded events and decisions.", path: "/admin/audit" },
    ],
    auditor: [
      { title: "Browse resources", description: "Inspect resources available in your read-only scope.", path: "/resources" },
      { title: "Audit timeline", description: "Review resource event history.", path: "/audit" },
      { title: "Profile", description: "View your account details.", path: "/profile" },
    ],
  };

  return (
    <div className="page-content">
      <TipTour role={user.role} />
      <PageHeading
        eyebrow={roleLabels[user.role].toUpperCase() + " WORKSPACE"}
        title={`Good to see you, ${user.display_name.split(" ")[0]}`}
        description="Choose a task to get started."
      />
      {error !== null && <ErrorState error={error} onRetry={() => setLoadVersion((version) => version + 1)} />}
      <div className="dashboard-action-grid">
        {actionsByRole[user.role].map((action, index) => action.assistant ? (
          <button
            className="dashboard-action-card"
            type="button"
            key={action.title}
            onClick={() => window.dispatchEvent(new Event("open-booking-assistant"))}
          >
            <span className="dashboard-action-number">0{index + 1}</span>
            <span className="dashboard-action-copy"><strong>{action.title}</strong><span>{action.description}</span></span>
            <span className="dashboard-action-arrow" aria-hidden="true">→</span>
          </button>
        ) : (
          <Link className="dashboard-action-card" to={action.path ?? "/dashboard"} key={action.title}>
            <span className="dashboard-action-number">0{index + 1}</span>
            <span className="dashboard-action-copy"><strong>{action.title}</strong><span>{action.description}</span></span>
            <span className="dashboard-action-arrow" aria-hidden="true">→</span>
          </Link>
        ))}
      </div>
      {!loading && user.role === "requester" && data && (
        <section className="what-next-card" aria-labelledby="what-next-title">
          <div><p className="eyebrow">WHAT TO DO NEXT</p><h2 id="what-next-title">{requesterNext.title}</h2><p>{requesterNext.detail}</p></div>
          <Link className="button button-primary" to={requesterNext.path}>{requesterNext.label}</Link>
        </section>
      )}
      {!loading && user.role === "lab_manager" && data && (
        <section className="what-next-card" aria-labelledby="what-next-title">
          <div><p className="eyebrow">WHAT TO DO NEXT</p><h2 id="what-next-title">{managerNext.title}</h2><p>{managerNext.detail}</p></div>
          <Link className="button button-primary" to={managerNext.path}>{managerNext.label}</Link>
        </section>
      )}
      {!loading && user.role === "institution_admin" && adminData && (
        <section className="what-next-card" aria-labelledby="what-next-title">
          <div>
            <p className="eyebrow">WHAT TO DO NEXT</p>
            <h2 id="what-next-title">{adminData.pendingApplications > 0 ? "Owner applications need review" : "No owner applications are waiting"}</h2>
            <p>{adminData.pendingApplications > 0
              ? `${adminData.pendingApplications} pending application${adminData.pendingApplications === 1 ? "" : "s"} · ${adminData.users} account${adminData.users === 1 ? "" : "s"} in the directory.`
              : `${adminData.users} account${adminData.users === 1 ? "" : "s"} in the directory. Review user access or inspect the audit.`}</p>
          </div>
          <Link className="button button-primary" to={adminData.pendingApplications > 0 ? "/admin/owner-applications" : "/admin/users"}>
            {adminData.pendingApplications > 0 ? "Review applications" : "Review users"}
          </Link>
        </section>
      )}
      {!loading && user.role === "auditor" && auditorResources !== null && (
        <section className="what-next-card" aria-labelledby="what-next-title">
          <div><p className="eyebrow">WHAT TO DO NEXT</p><h2 id="what-next-title">{auditorResources.total > 0 ? "Review the resource audit trail" : "No resources are available to inspect"}</h2><p>{auditorResources.total} resource{auditorResources.total === 1 ? "" : "s"} are available in your read-only catalog.</p></div>
          <Link className="button button-primary" to={auditorResources.total > 0 ? "/audit" : "/resources"}>{auditorResources.total > 0 ? "Open audit timeline" : "Browse resources"}</Link>
        </section>
      )}
      {loading && <div className="skeleton-grid dashboard-loading" aria-label="Loading dashboard"><span className="skeleton skeleton-metric" /><span className="skeleton skeleton-metric" /><span className="skeleton skeleton-metric" /></div>}
      {data && (user.role === "lab_manager" || user.role === "requester") && (
        <>
          <div className="dashboard-metrics">
            {Object.entries(data.summary).map(([key, value]) => (
              <StatCard label={key.replaceAll("_", " ")} value={value} key={key} />
            ))}
          </div>
          {user.role === "requester" ? (
            <div className="requester-dashboard-grid">
              <Card className="dashboard-up-next">
                <div className="card-title-row"><h2>Upcoming bookings</h2><Link className="text-link" to="/bookings">View bookings →</Link></div>
                {upcomingBookings.length ? <ul className="up-next-list">{upcomingBookings.map(({ request, booking }) => booking && <li key={booking.id}><span className="up-next-mark" aria-hidden="true">•</span><div><strong>{request.purpose.replaceAll("_", " ")}</strong><p>{formatIST(booking.start_at)} · {booking.status.replaceAll("_", " ").toLowerCase()}</p></div>{request.is_demo && <Badge>Sample data</Badge>}</li>)}</ul> : <EmptyState title="No upcoming bookings">Confirmed sessions will appear here.</EmptyState>}
              </Card>
              <Card className="dashboard-up-next">
                <div className="card-title-row"><h2>Pending requests</h2><Link className="text-link" to="/requests">View requests →</Link></div>
                {pendingRequests.length ? <ul className="up-next-list">{pendingRequests.map(({ request }) => <li key={request.id}><span className="up-next-mark" aria-hidden="true">•</span><div><strong>{request.purpose.replaceAll("_", " ")}</strong><p>{formatIST(request.start_at)} · {request.status.replaceAll("_", " ").toLowerCase()}</p></div>{request.is_demo && <Badge>Sample data</Badge>}</li>)}</ul> : <EmptyState title="No pending requests">New manager decisions will show up here.</EmptyState>}
              </Card>
              <Card className="dashboard-up-next">
                <h2>Training expiring soon ({data.summary.expiring_training ?? 0})</h2>
                {expiringTraining.length ? <ul className="up-next-list">{expiringTraining.map((item) => <li key={item.id}><span className="up-next-mark" aria-hidden="true">•</span><div><strong>{item.title}</strong><p>{item.at ? formatIST(item.at) : "Expiry date not provided"}</p></div><StatusBadge value={item.status} /></li>)}</ul> : (data.summary.expiring_training ?? 0) > 0 ? <p className="helper">The dashboard reports {data.summary.expiring_training} expiring records, but did not include their details in its five next items.</p> : <EmptyState title="No upcoming expiries">The dashboard reports no expiring training in the current window.</EmptyState>}
              </Card>
              <Card className="dashboard-up-next">
                <div className="card-title-row"><h2>Notifications</h2><span>{notifications.filter((item) => !item.read_at).length} unread</span></div>
                {notifications.length ? <ul className="up-next-list">{notifications.slice(0, 5).map((item) => <li key={item.id}><span className="up-next-mark" aria-hidden="true">•</span><div><strong>{item.type.replaceAll("_", " ")}</strong><p>{formatIST(item.created_at)}</p></div>{item.is_demo && <Badge>Sample data</Badge>}</li>)}</ul> : <EmptyState title="No notifications">The notifications API returned no items.</EmptyState>}
              </Card>
            </div>
          ) : (
            <div className="manager-dashboard">
            <Card className="dashboard-up-next">
              <div className="card-title-row"><div><p className="eyebrow">KEEP MOVING</p><h2>Up next</h2></div><Link className="text-link" to="/manager/requests">View all <span aria-hidden="true">→</span></Link></div>
              {data.next_items.length ? <ul className="up-next-list">{data.next_items.map((item) => <li key={`${item.type}-${item.id}`}><span className="up-next-mark" aria-hidden="true">•</span><div><strong>{item.title}</strong><p>{item.at ? new Date(item.at).toLocaleString() : "Date not provided"} <span aria-hidden="true">·</span> {item.status.replaceAll("_", " ").toLowerCase()}</p></div><Badge>{item.type.replaceAll("_", " ")}</Badge></li>)}</ul> : <EmptyState title="Nothing needs attention">Your upcoming work will appear here.</EmptyState>}
            </Card>
            <Card className="dashboard-up-next">
              <h2>Quick links</h2><div className="card-actions"><Link className="button button-secondary" to="/manager/resources">Manage resources</Link><Link className="button button-secondary" to="/manager/sessions">Sessions</Link><Link className="button button-secondary" to="/manager/training">Training sign-off</Link><Link className="button button-secondary" to="/manager/incidents">Open incidents</Link></div>
              <p className="helper">The current dashboard API does not include expiring-policy records; no policy expiry count is inferred.</p>
            </Card>
            </div>
          )}
        </>
      )}
      {!loading && user.role === "institution_admin" && adminData && (
        <div className="dashboard-metrics">
          <StatCard label="Accounts" value={adminData.users} />
          <StatCard label="Pending owner applications" value={adminData.pendingApplications} />
          <StatCard label="Owner applications" value={adminData.applications} />
        </div>
      )}
      {!loading && user.role === "auditor" && auditorResources && (
        <div className="dashboard-metrics">
          <StatCard label="Resources in catalog" value={auditorResources.total} />
          <StatCard label="Active resources" value={auditorResources.active} />
          <StatCard label="Resources needing review" value={auditorResources.needsReview} detail="Catalog readiness checks only" />
        </div>
      )}
    </div>
  );
}

function NotFoundPage() {
  return (
    <main className="page-content not-found-page">
      <p className="eyebrow">404 · PAGE NOT FOUND</p>
      <h1>We can’t find that page.</h1>
      <p className="muted">The link may be incorrect or the page may have moved.</p>
      <Link className="button button-primary" to="/">Return to OpenVault</Link>
    </main>
  );
}

interface BoundaryState {
  hasError: boolean;
}

class ErrorBoundary extends Component<{ children: ReactNode }, BoundaryState> {
  state: BoundaryState = { hasError: false };

  static getDerivedStateFromError(): BoundaryState {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="page-content error-boundary">
          <Alert tone="danger" title="This page ran into a problem">Your information has not been changed. Try reloading this page.</Alert>
          <Button type="button" onClick={() => window.location.reload()}>Reload page</Button>
        </main>
      );
    }
    return this.props.children;
  }
}

function ProtectedLayout() {
  const { user, loading, judgeMode } = useAuth();
  const location = useLocation();
  if (loading) return <div className="page-loading"><span className="skeleton skeleton-block" role="status" aria-label="Checking your session" /></div>;
  if (!user) {
    const protectedPath = /^\/(?:dashboard|resources|requests|bookings|contracts|manager|audit|admin|profile)(?:\/|$)/.test(location.pathname);
    return protectedPath ? <Navigate to="/login" replace /> : <NotFoundPage />;
  }
  return (
    <div className="workspace">
      <AppHeader user={user} />
      {judgeMode && <JudgeGuide role={user.role} />}
      <Routes>
        <Route path="/dashboard" element={<DashboardPage user={user} />} />
        <Route path="/resources" element={<ResourcesPage />} />
        <Route path="/resources/:resourceId" element={<ResourceDetailPage role={user.role} />} />
        <Route path="/resources/:resourceId/memory" element={<ResourceMemoryPage />} />
        <Route path="/requests" element={user.role === "requester" ? <RequestsPage /> : <Navigate to="/dashboard" replace />} />
        <Route path="/bookings" element={user.role === "requester" ? <MyBookingsPage /> : <Navigate to="/dashboard" replace />} />
        <Route path="/bookings/:bookingId" element={user.role === "requester" ? <BookingDetailPage /> : <Navigate to="/dashboard" replace />} />
        <Route path="/contracts/:bookingId" element={user.role === "requester" ? <ContractPage /> : <Navigate to="/dashboard" replace />} />
        <Route path="/manager/requests" element={user.role === "lab_manager" ? <ManagerQueuePage /> : <Navigate to="/dashboard" replace />} />
        <Route path="/manager/resources" element={user.role === "lab_manager" ? <ResourceManagementPage /> : <Navigate to="/dashboard" replace />} />
        <Route path="/manager/sessions" element={user.role === "lab_manager" ? <ManagerSessionsPage /> : <Navigate to="/dashboard" replace />} />
        <Route path="/manager/training" element={user.role === "lab_manager" ? <TrainingPage /> : <Navigate to="/dashboard" replace />} />
        <Route path="/manager/incidents" element={user.role === "lab_manager" ? <IncidentListPage /> : <Navigate to="/dashboard" replace />} />
        <Route path="/manager/incidents/:incidentId" element={user.role === "lab_manager" ? <IncidentDetailPage /> : <Navigate to="/dashboard" replace />} />
        <Route path="/audit" element={<AuditTimelinePage />} />
        <Route path="/admin/owner-applications" element={user.role === "institution_admin" ? <AdminOwnerApplicationsPage /> : <Navigate to="/dashboard" replace />} />
        <Route path="/admin/users" element={user.role === "institution_admin" ? <AdminUsersPage /> : <Navigate to="/dashboard" replace />} />
        <Route path="/admin/audit" element={user.role === "institution_admin" ? <AdminAuditExplorerPage /> : <Navigate to="/dashboard" replace />} />
        <Route path="/admin" element={user.role === "institution_admin" ? <AdminPage /> : <Navigate to="/dashboard" replace />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      <BookingAssistant role={user.role} />
    </div>
  );
}

function RouterView() {
  const { user, loading } = useAuth();
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={loading ? <div className="page-loading"><span className="skeleton skeleton-block" role="status" aria-label="Checking your session" /></div> : user ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
      <Route path="/signup" element={loading ? <div className="page-loading"><span className="skeleton skeleton-block" role="status" aria-label="Checking your session" /></div> : user ? <Navigate to="/dashboard" replace /> : <SignupPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/*" element={<ProtectedLayout />} />
    </Routes>
  );
}

function AppContent() {
  const { backendWaking } = useAuth();
  return (
    <>
      {backendWaking && (
        <div className="backend-waking-notice" role="status" aria-live="polite">
          The demo server is waking up, this can take up to a minute.
        </div>
      )}
      <ErrorBoundary><RouterView /></ErrorBoundary>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </BrowserRouter>
  );
}
