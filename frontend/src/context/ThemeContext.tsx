import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  getTheme,
  resolveTheme,
  setTheme,
  toggleTheme,
  type Theme,
} from "../lib/theme";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => resolveTheme());

  useEffect(() => {
    const onChange = (e: Event) => {
      const detail = (e as CustomEvent<Theme>).detail;
      if (detail === "light" || detail === "dark") {
        setThemeState(detail);
      } else {
        setThemeState(getTheme());
      }
    };
    window.addEventListener("fairdatahive-theme-change", onChange);
    return () =>
      window.removeEventListener("fairdatahive-theme-change", onChange);
  }, []);

  const setThemeValue = useCallback((next: Theme) => {
    setTheme(next);
    setThemeState(next);
  }, []);

  const toggle = useCallback(() => {
    const next = toggleTheme();
    setThemeState(next);
  }, []);

  const value = useMemo(
    () => ({ theme, setTheme: setThemeValue, toggleTheme: toggle }),
    [theme, setThemeValue, toggle]
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return ctx;
}
