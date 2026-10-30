import { useState } from "react";
import {
  BrowserRouter,
  Link,
  Navigate,
  NavLink,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import { ApiError } from "./api/client";
import type { Role } from "./api/types";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { ErrorState, Loading } from "./components/Feedback";
import { ResourceDetailPage, ResourcesPage } from "./pages/ResourcesPage";
import { ContractPage, RequestsPage } from "./pages/RequestsPage";
import { IncidentDetailPage, IncidentListPage, ManagerQueuePage, TrainingPage } from "./pages/ManagerPages";
import { AdminPage, AuditTimelinePage, ResourceMemoryPage } from "./pages/AuditMemoryPages";

function LoginPage() {
  const { accounts, loading, accountsError, signIn } = useAuth();
  const [password, setPassword] = useState("northstar-demo");
  const [error, setError] = useState<unknown>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const navigate = useNavigate();

  async function login(accountId: string) {
    setPendingId(accountId);
    setError(null);
    try {
      await signIn(accountId, password);
      navigate("/", { replace: true });
    } catch (loginError) {
      setError(loginError);
    } finally {
      setPendingId(null);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <p className="eyebrow">NORTHSTAR ENGINEERING LAB</p>
        <h1 id="login-title">OpenVault</h1>
        <p className="muted">Sign in with a seeded demo account.</p>
        <label className="field-label" htmlFor="demo-password">
          Shared demo password
        </label>
        <input
          id="demo-password"
          className="input"
          type="text"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <p className="helper">Visible demo password: northstar-demo</p>
        {error !== null && <ErrorState error={error} />}
        {accountsError && <ErrorState error={new ApiError(0, "load_error", accountsError)} />}
        {loading ? (
          <Loading label="Checking your session and loading demo accounts…" />
        ) : accounts.length === 0 ? (
          <p className="feedback">No demo accounts are available.</p>
        ) : (
          <div className="mt-5 grid gap-2">
            {accounts.map((account) => (
              <button
                className="button button-secondary w-full justify-between"
                key={account.id}
                type="button"
                disabled={pendingId !== null}
                onClick={() => void login(account.id)}
              >
                <span>{account.display_name}</span>
                <span className="role-text">{pendingId === account.id ? "Signing in…" : account.role}</span>
              </button>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

const roleLabels: Record<Role, string> = {
  requester: "Requester",
  lab_manager: "Lab Manager",
  institution_admin: "Institution Admin",
  auditor: "Judge Auditor",
};

function ProtectedLayout() {
  const { user, loading, signOut } = useAuth();
  const [logoutError, setLogoutError] = useState<unknown>(null);
  const navigate = useNavigate();

  if (loading) return <Loading label="Checking session…" />;
  if (!user) return <Navigate to="/login" replace />;

  async function logout() {
    try {
      await signOut();
      navigate("/login", { replace: true });
    } catch (error) {
      setLogoutError(error);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" to="/">OpenVault</Link>
        <p className="sidebar-caption">NORTHSTAR ENGINEERING LAB</p>
        <nav className="nav-links" aria-label="Main navigation">
          <NavLink to="/resources">Resources</NavLink>
          {user.role === "requester" && <NavLink to="/requests">My requests</NavLink>}
          {user.role === "lab_manager" && (
            <>
              <NavLink to="/manager/requests">Manager queue</NavLink>
              <NavLink to="/manager/training">Training sign-off</NavLink>
              <NavLink to="/manager/incidents">Incidents</NavLink>
            </>
          )}
          <NavLink to="/audit">Audit timeline</NavLink>
          {user.role === "institution_admin" && <NavLink to="/admin">Admin</NavLink>}
        </nav>
        <div className="sidebar-user">
          <span className="avatar" aria-hidden="true">{user.display_name.slice(0, 1)}</span>
          <div className="min-w-0">
            <p className="truncate font-semibold">{user.display_name}</p>
            <p className="muted">{roleLabels[user.role]}</p>
          </div>
          <button className="button button-quiet" type="button" onClick={() => void logout()}>
            Log out
          </button>
        </div>
      </aside>
      <div className="main-column">
        <div className="demo-banner" role="note">
          <strong>DEMO DATA</strong>
          <span>Seeded sample records — not live institutional data.</span>
        </div>
        <main className="page-content">
          {logoutError !== null && <ErrorState error={logoutError} />}
          <Routes>
            <Route path="/" element={<Navigate to="/resources" replace />} />
            <Route path="/resources" element={<ResourcesPage />} />
            <Route path="/resources/:resourceId" element={<ResourceDetailPage role={user.role} />} />
            <Route path="/resources/:resourceId/memory" element={<ResourceMemoryPage />} />
            <Route path="/requests" element={user.role === "requester" ? <RequestsPage /> : <Navigate to="/resources" replace />} />
            <Route path="/contracts/:bookingId" element={user.role === "requester" ? <ContractPage /> : <Navigate to="/resources" replace />} />
            <Route path="/manager/requests" element={user.role === "lab_manager" ? <ManagerQueuePage /> : <Navigate to="/resources" replace />} />
            <Route path="/manager/training" element={user.role === "lab_manager" ? <TrainingPage /> : <Navigate to="/resources" replace />} />
            <Route path="/manager/incidents" element={user.role === "lab_manager" ? <IncidentListPage /> : <Navigate to="/resources" replace />} />
            <Route path="/manager/incidents/:incidentId" element={user.role === "lab_manager" ? <IncidentDetailPage /> : <Navigate to="/resources" replace />} />
            <Route path="/audit" element={<AuditTimelinePage />} />
            <Route path="/admin" element={user.role === "institution_admin" ? <AdminPage /> : <Navigate to="/resources" replace />} />
            <Route path="*" element={<Placeholder title="OpenVault" />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function Placeholder({ title }: { title: string }) {
  return (
    <section className="page-heading">
      <p className="eyebrow">OPENVAULT</p>
      <h1>{title}</h1>
      <p className="muted">Your workspace is ready.</p>
    </section>
  );
}

function RouterView() {
  const { user, loading } = useAuth();
  return (
    <Routes>
      <Route
        path="/login"
        element={loading ? <Loading label="Checking session…" /> : user ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route path="/*" element={<ProtectedLayout />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <RouterView />
      </AuthProvider>
    </BrowserRouter>
  );
}
