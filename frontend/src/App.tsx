import { Component, useEffect, useMemo, useState, type ReactNode } from "react";
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
import type { Role, User } from "./api/types";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { ErrorState } from "./components/Feedback";
import { Alert, Badge, Button, Card, EmptyState } from "./components/UI";
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
  lab_manager: "Resource owner",
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
  const { signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [logoutError, setLogoutError] = useState<unknown>(null);
  const navItems = [
    { path: "/resources", label: "Resources", show: true },
    { path: "/requests", label: "My requests", show: user.role === "requester" },
    { path: "/bookings", label: "My bookings", show: user.role === "requester" },
    { path: "/manager/requests", label: "Requests", show: user.role === "lab_manager" },
    { path: "/manager/resources", label: "Manage resources", show: user.role === "lab_manager" },
    { path: "/manager/sessions", label: "Sessions", show: user.role === "lab_manager" },
    { path: "/manager/training", label: "Training", show: user.role === "lab_manager" },
    { path: "/manager/incidents", label: "Incidents", show: user.role === "lab_manager" },
    { path: "/audit", label: "Audit", show: true },
    { path: "/admin/owner-applications", label: "Owner applications", show: user.role === "institution_admin" },
    { path: "/admin/users", label: "Users", show: user.role === "institution_admin" },
    { path: "/admin/audit", label: "Audit explorer", show: user.role === "institution_admin" },
    { path: "/admin", label: "Demo reset", show: user.role === "institution_admin" },
  ].filter((item) => item.show);

  async function logout() {
    setLogoutError(null);
    try {
      await signOut();
      navigate("/login", { replace: true });
    } catch (error) {
      setLogoutError(error);
    }
  }

  useEffect(() => { setMenuOpen(false); }, [location.pathname]);

  return (
    <>
      <header className="app-header">
        <Link className="brand" to="/resources" aria-label="OpenVault workspace">openvault<span aria-hidden="true">.</span></Link>
        <button className="mobile-menu-toggle" type="button" aria-expanded={menuOpen} aria-controls="primary-navigation" onClick={() => setMenuOpen((open) => !open)}>
          <span aria-hidden="true">{menuOpen ? "×" : "☰"}</span><span className="sr-only">{menuOpen ? "Close menu" : "Open menu"}</span>
        </button>
        <nav className={`app-nav ${menuOpen ? "app-nav-open" : ""}`} id="primary-navigation" aria-label="Main navigation">
          {navItems.map((item) => (
            <NavLink key={item.path} to={item.path} end={item.path === "/resources"} className={({ isActive }) => `app-nav-link ${isActive ? "active" : ""}`}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="header-actions">
          <NotificationBell role={user.role} />
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

interface DashboardProfile {
  intended_use: string | null;
}

interface DashboardRecommendation {
  resource_id: string;
  explanation: string;
  name: string;
  location: string;
  ready: boolean;
}

const dashboardMetricDetails: Record<string, { label: string; detail: string }> = {
  upcoming_bookings: { label: "Upcoming bookings", detail: "Sessions on your calendar" },
  pending_requests: { label: "Pending requests", detail: "Waiting for a resource owner" },
  open_incidents: { label: "Open incidents", detail: "Items needing follow-up" },
  expiring_training: { label: "Training expiring", detail: "Within the next 30 days" },
};

function DashboardPage({ user }: { user: User }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [requests, setRequests] = useState<DashboardRequestRecord[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [profile, setProfile] = useState<DashboardProfile | null>(null);
  const [recommendations, setRecommendations] = useState<DashboardRecommendation[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    if (user.role !== "lab_manager" && user.role !== "requester") {
      setLoading(false);
      return () => { active = false; };
    }
    const path = user.role === "lab_manager" ? "/dashboard/manager" : "/dashboard/requester";
    const loads = user.role === "requester"
      ? Promise.all([
        api.get<DashboardData>(path),
        api.get<{ items: DashboardRequestRecord[] }>("/requests/mine"),
        api.get<{ items: NotificationItem[] }>("/notifications"),
        api.get<DashboardProfile>("/me"),
      ]).then(async ([dashboard, history, notificationList, account]) => {
        if (!active) return;
        setData(dashboard);
        setRequests(history.items);
        setNotifications(notificationList.items);
        setProfile(account);
        if (account.intended_use?.trim()) {
          try {
            const [matches, catalog] = await Promise.all([
              api.post<{ candidates: Array<{ resource_id: string; explanation: string }> }>(
                "/ai/match",
                { goal: account.intended_use, constraints: {} },
              ),
              api.get<{ items: Array<{ id: string; name: string; location: string; readiness: { ready: boolean } }> }>("/resources?sort=next_availability"),
            ]);
            if (!active) return;
            const resources = new Map(catalog.items.map((resource) => [resource.id, resource]));
            setRecommendations(matches.candidates.flatMap((candidate) => {
              const resource = resources.get(candidate.resource_id);
              return resource ? [{
                resource_id: resource.id,
                name: resource.name,
                location: resource.location,
                ready: resource.readiness.ready,
                explanation: candidate.explanation,
              }] : [];
            }).slice(0, 3));
          } catch {
            if (active) setRecommendations([]);
          }
        }
      })
      : api.get<DashboardData>(path).then((dashboard) => active && setData(dashboard));
    void loads.catch((loadError: unknown) => active && setError(loadError))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [user.role]);
  const upcomingBookings = requests
    .filter((item) => item.booking && ["CONFIRMED", "CHECKED_IN", "NO_SHOW"].includes(item.booking.status) && new Date(item.booking.end_at).getTime() >= Date.now())
    .sort((a, b) => new Date(a.booking!.start_at).getTime() - new Date(b.booking!.start_at).getTime())
    .slice(0, 5);
  const pendingRequests = requests
    .filter((item) => ["PENDING_REVIEW", "WAITLISTED"].includes(item.request.status))
    .sort((a, b) => new Date(a.request.start_at).getTime() - new Date(b.request.start_at).getTime())
    .slice(0, 5);
  const expiringTraining = data?.next_items.filter((item) => item.type === "expiring_training") ?? [];

  return (
    <div className="page-content dashboard-page">
      <header className="dashboard-welcome">
        <div>
          <p className="eyebrow">{new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" }).format(new Date())} <span aria-hidden="true">·</span> {roleLabels[user.role]}</p>
          <h1>Good to see you, {user.display_name.split(" ")[0]}.</h1>
          <p>{user.role === "lab_manager" ? "Your resources, incoming decisions and follow-up work." : "Your access, upcoming sessions and next steps."}</p>
        </div>
        <Link className="dashboard-profile-link" to="/profile">
          <span className="dashboard-profile-avatar" aria-hidden="true">{user.display_name.slice(0, 1).toUpperCase()}</span>
          <span><strong>Profile & preferences</strong><small>{profile?.intended_use ? "Discovery profile is active" : "Add a goal to personalize matches"}</small></span>
          <span aria-hidden="true">↗</span>
        </Link>
      </header>
      {error !== null && <ErrorState error={error} />}
      {user.role === "institution_admin" || user.role === "auditor" ? <Card className="dashboard-up-next">
        <h2>{user.role === "auditor" ? "Read-only records" : "Administration"}</h2>
        <p>{user.role === "auditor" ? "This account can inspect scoped audit history and resource records. Management actions are not available." : "Use the administration tools to review owner applications, view users and explore audit events."}</p>
        <div className="card-actions"><Link className="button button-secondary" to="/audit">Open audit history</Link>{user.role === "institution_admin" && <Link className="button button-primary" to="/admin/owner-applications">Review owner applications</Link>}</div>
      </Card> : loading ? <div className="skeleton-grid" aria-label="Loading dashboard"><span className="skeleton skeleton-metric" /><span className="skeleton skeleton-metric" /><span className="skeleton skeleton-metric" /><span className="skeleton skeleton-metric" /></div> : data && (
        <>
          <div className="dashboard-metrics">
            {Object.entries(data.summary).map(([key, value], index) => {
              const metric = dashboardMetricDetails[key] ?? { label: key.replaceAll("_", " "), detail: "Current total" };
              return (
                <Card className={`dashboard-metric dashboard-metric-${key}`} key={key}>
                  <span className="dashboard-metric-index">0{index + 1}</span>
                  <strong>{value}</strong>
                  <div><p>{metric.label}</p><small>{metric.detail}</small></div>
                </Card>
              );
            })}
          </div>
          {user.role === "requester" ? (
            <div className="requester-dashboard-grid">
              <Card className="dashboard-recommendations">
                <div className="card-title-row"><div><p className="eyebrow">PERSONALIZED DISCOVERY</p><h2>Picked for your goals</h2></div><Link className="text-link" to="/resources">Explore all →</Link></div>
                {profile?.intended_use ? recommendations.length ? (
                  <>
                    <p className="dashboard-algorithm-note">Ranked against your stated goal, resource capabilities and readiness. Final eligibility is checked when you choose a time.</p>
                    <ul className="recommendation-list-dashboard">{recommendations.map((resource, index) => (
                      <li key={resource.resource_id}>
                        <span className="recommendation-rank">0{index + 1}</span>
                        <div><Link to={`/resources/${resource.resource_id}`}><strong>{resource.name}</strong></Link><small>{resource.location}</small><small>{resource.explanation}</small></div>
                        <Badge tone={resource.ready ? "success" : "warning"}>{resource.ready ? "Ready to check" : "Review access"}</Badge>
                      </li>
                    ))}</ul>
                  </>
                ) : <EmptyState title="No close matches yet">Try a broader goal or browse the full catalog.</EmptyState> : (
                  <div className="dashboard-profile-prompt"><p>Add what you want to use OpenVault for and your dashboard can rank relevant resources for you.</p><Link className="button button-secondary" to="/profile">Set discovery goal</Link></div>
                )}
              </Card>
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
                {expiringTraining.length ? <ul className="up-next-list">{expiringTraining.map((item) => <li key={item.id}><span className="up-next-mark" aria-hidden="true">•</span><div><strong>{item.title}</strong><p>{item.at ? formatIST(item.at) : "Expiry date not provided"}</p></div><Badge>{item.status.replaceAll("_", " ")}</Badge></li>)}</ul> : (data.summary.expiring_training ?? 0) > 0 ? <p className="helper">The dashboard reports {data.summary.expiring_training} expiring records, but did not include their details in its five next items.</p> : <EmptyState title="No upcoming expiries">The dashboard reports no expiring training in the current window.</EmptyState>}
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
      {user.role === "requester" && <div className="dashboard-cta"><Card><p className="eyebrow">RESOURCE CATALOG</p><h2>Looking for something?</h2><p>Browse available equipment and spaces, then review their requirements.</p><Link className="button button-primary" to="/resources">Explore resources <span aria-hidden="true">→</span></Link></Card></div>}
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
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="page-loading"><span className="skeleton skeleton-block" role="status" aria-label="Checking your session" /></div>;
  if (!user) {
    const protectedPath = /^\/(?:dashboard|resources|requests|bookings|contracts|manager|audit|admin|profile)(?:\/|$)/.test(location.pathname);
    return protectedPath ? <Navigate to="/login" replace /> : <NotFoundPage />;
  }
  return (
    <div className="workspace">
      <AppHeader user={user} />
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

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ErrorBoundary><RouterView /></ErrorBoundary>
      </AuthProvider>
    </BrowserRouter>
  );
}
