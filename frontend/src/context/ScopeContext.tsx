import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type CatalogScope = "public" | "project";

interface ScopeContextValue {
  mode: CatalogScope;
  projectId: string;
  apiScope: string;
  setMode: (m: CatalogScope) => void;
  setProjectId: (id: string) => void;
}

const ScopeContext = createContext<ScopeContextValue | null>(null);

const PROJECT_KEY = "fairdatahive_project_id";

export function ScopeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<CatalogScope>("public");
  const [projectId, setProjectIdState] = useState(
    () => localStorage.getItem(PROJECT_KEY) || ""
  );

  const setProjectId = useCallback((id: string) => {
    setProjectIdState(id);
    if (id) localStorage.setItem(PROJECT_KEY, id);
    else localStorage.removeItem(PROJECT_KEY);
  }, []);

  const apiScope = mode === "public" ? "public" : projectId.trim() || "public";

  const value = useMemo(
    () => ({ mode, projectId, apiScope, setMode, setProjectId }),
    [mode, projectId, apiScope, setProjectId]
  );

  return (
    <ScopeContext.Provider value={value}>{children}</ScopeContext.Provider>
  );
}

export function useScope() {
  const ctx = useContext(ScopeContext);
  if (!ctx) throw new Error("useScope must be used within ScopeProvider");
  return ctx;
}
