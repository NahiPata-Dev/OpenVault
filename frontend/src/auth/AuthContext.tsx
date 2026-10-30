import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "../api/client";
import type { DemoAccount, User } from "../api/types";

interface AuthContextValue {
  user: User | null;
  accounts: DemoAccount[];
  loading: boolean;
  accountsError: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signInDemo: (accountId: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accounts, setAccounts] = useState<DemoAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [accountsError, setAccountsError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void Promise.all([
      api.get<{ user: User }>("/auth/session").then(
        ({ user: sessionUser }) => active && setUser(sessionUser),
        () => active && setUser(null),
      ),
      api.get<{ accounts: DemoAccount[] }>("/auth/demo-accounts").then(
        ({ accounts: demoAccounts }) => active && setAccounts(demoAccounts),
        (error: Error) => active && setAccountsError(error.message),
      ),
    ]).finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await api.post<{ user: User }>("/auth/login", {
      email,
      password,
    });
    setUser(result.user);
  }, []);

  const signInDemo = useCallback(async (accountId: string, password: string) => {
    const result = await api.post<{ user: User }>("/auth/demo-login", {
      account_id: accountId,
      password,
    });
    setUser(result.user);
  }, []);

  const signOut = useCallback(async () => {
    await api.post<{ ok: boolean }>("/auth/logout");
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, accounts, loading, accountsError, signIn, signInDemo, signOut }),
    [user, accounts, loading, accountsError, signIn, signInDemo, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
