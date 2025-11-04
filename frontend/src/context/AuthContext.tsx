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
import type { UserProfile } from "../types";

interface AuthContextValue {
  token: string | null;
  setToken: (t: string | null) => void;
  profile: UserProfile | null;
  loading: boolean;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const STORAGE_KEY = "fairdatahive_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const devDefault =
    import.meta.env.VITE_DEV_AUTH === "true" ? "dev" : null;

  const [token, setTokenState] = useState<string | null>(() => {
    return localStorage.getItem(STORAGE_KEY) || devDefault;
  });
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const setToken = useCallback((t: string | null) => {
    setTokenState(t);
    if (t) localStorage.setItem(STORAGE_KEY, t);
    else localStorage.removeItem(STORAGE_KEY);
  }, []);

  const refreshProfile = useCallback(async () => {
    if (!token) {
      setProfile(null);
      return;
    }
    try {
      const p = await api.me();
      setProfile(p);
    } catch {
      setProfile(null);
    }
  }, [token]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      if (token) {
        try {
          const p = await api.me();
          if (!cancelled) setProfile(p);
        } catch {
          if (!cancelled) setProfile(null);
        }
      } else if (!cancelled) {
        setProfile(null);
      }
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const value = useMemo(
    () => ({ token, setToken, profile, loading, refreshProfile }),
    [token, setToken, profile, loading, refreshProfile]
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
