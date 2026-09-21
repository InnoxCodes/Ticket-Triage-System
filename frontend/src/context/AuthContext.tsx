import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, ApiError, onUnauthorized, setAuthToken } from "@/lib/api";
import { TOKEN_STORAGE_KEY } from "@/lib/constants";
import type { Agent } from "@/lib/types";

export type AuthStatus = "checking" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: AuthStatus;
  agent: Agent | null;
  token: string | null;
  login: (email: string, password: string) => Promise<Agent>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

// The token lives in localStorage rather than an httpOnly cookie. With the
// frontend and API on different origins, a cookie would need SameSite=None plus
// CSRF tokens; for an internal agent tool a bearer token is the simpler trade.
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string | null>(readStoredToken);
  const [agent, setAgent] = useState<Agent | null>(null);
  const [status, setStatus] = useState<AuthStatus>(() =>
    readStoredToken() ? "checking" : "anonymous",
  );

  const logout = useCallback(() => {
    try {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    } catch {
      // Nothing to clear if storage is unavailable.
    }
    setAuthToken(null);
    setToken(null);
    setAgent(null);
    setStatus("anonymous");
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    const stored = readStoredToken();
    if (!stored) return;

    setAuthToken(stored);
    let cancelled = false;

    api
      .me()
      .then((me) => {
        if (cancelled) return;
        setAgent(me);
        setStatus("authenticated");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        // Only a rejected token ends the session. If the API is merely
        // unreachable, keep the token so the next load can try again.
        if (error instanceof ApiError && error.status === 401) logout();
        else setStatus("anonymous");
      });

    return () => {
      cancelled = true;
    };
  }, [logout]);

  useEffect(() => {
    onUnauthorized(logout);
    return () => onUnauthorized(null);
  }, [logout]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await api.login(email, password);
    try {
      localStorage.setItem(TOKEN_STORAGE_KEY, response.access_token);
    } catch {
      // Session still works for this tab without persistence.
    }
    setAuthToken(response.access_token);
    setToken(response.access_token);
    setAgent(response.agent);
    setStatus("authenticated");
    return response.agent;
  }, []);

  const value = useMemo(
    () => ({ status, agent, token, login, logout }),
    [status, agent, token, login, logout],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
