import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiError, api } from "../api/client";
import type { JudgeRole, User } from "../api/types";

interface SessionResponse {
  user: User | null;
  judge_mode: boolean;
  judge_login_available: boolean;
  available_judge_roles: JudgeRole[];
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  backendWaking: boolean;
  judgeMode: boolean;
  judgeLoginAvailable: boolean;
  availableJudgeRoles: JudgeRole[];
  signIn: (email: string, password: string) => Promise<void>;
  signInJudge: (role: JudgeRole) => Promise<void>;
  switchJudgeRole: (role: JudgeRole) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function isRetryable(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 0 || error.status >= 500);
}

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [backendWaking, setBackendWaking] = useState(false);
  const [judgeMode, setJudgeMode] = useState(false);
  const [judgeLoginAvailable, setJudgeLoginAvailable] = useState(false);
  const [availableJudgeRoles, setAvailableJudgeRoles] = useState<JudgeRole[]>([]);

  useEffect(() => {
    let active = true;
    const wakingTimer = window.setTimeout(() => {
      if (active) setBackendWaking(true);
    }, 2000);

    async function loadSession() {
      try {
        let session: SessionResponse | null = null;
        for (let attempt = 0; attempt < 5; attempt += 1) {
          try {
            session = await api.getWithTimeout<SessionResponse>(
              "/auth/session",
              8000,
            );
            break;
          } catch (error) {
            if (error instanceof ApiError && error.status === 401) break;
            if (!isRetryable(error) || attempt === 4) break;
            await wait(1000 * 2 ** attempt);
          }
        }
        if (!active) return;
        setUser(session?.user ?? null);
        setJudgeMode(session?.judge_mode ?? false);
        setJudgeLoginAvailable(session?.judge_login_available ?? false);
        setAvailableJudgeRoles(session?.available_judge_roles ?? []);
      } finally {
        if (active) {
          window.clearTimeout(wakingTimer);
          setBackendWaking(false);
          setLoading(false);
        }
      }
    }

    void loadSession();
    return () => {
      active = false;
      window.clearTimeout(wakingTimer);
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await api.post<{ user: User }>("/auth/login", {
      email,
      password,
    });
    setUser(result.user);
    setJudgeMode(false);
  }, []);

  const signInJudge = useCallback(async (role: JudgeRole) => {
    const result = await api.post<{ user: User }>("/auth/judge-login", { role });
    setUser(result.user);
    setJudgeMode(true);
  }, []);

  const switchJudgeRole = useCallback(async (role: JudgeRole) => {
    const result = await api.post<{ user: User }>("/auth/judge-switch", { role });
    setUser(result.user);
    setJudgeMode(true);
  }, []);

  const signOut = useCallback(async () => {
    await api.post<{ ok: boolean }>("/auth/logout");
    setUser(null);
    setJudgeMode(false);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      backendWaking,
      judgeMode,
      judgeLoginAvailable,
      availableJudgeRoles,
      signIn,
      signInJudge,
      switchJudgeRole,
      signOut,
    }),
    [
      user,
      loading,
      backendWaking,
      judgeMode,
      judgeLoginAvailable,
      availableJudgeRoles,
      signIn,
      signInJudge,
      switchJudgeRole,
      signOut,
    ],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
