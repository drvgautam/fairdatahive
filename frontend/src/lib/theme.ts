export type Theme = "light" | "dark";

export const THEME_STORAGE_KEY = "fairdatahive-theme";

export function resolveTheme(): Theme {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
}

export function getTheme(): Theme {
  const current = document.documentElement.getAttribute("data-theme");
  return current === "light" ? "light" : "dark";
}

export function setTheme(theme: Theme): void {
  localStorage.setItem(THEME_STORAGE_KEY, theme);
  applyTheme(theme);
  window.dispatchEvent(
    new CustomEvent("fairdatahive-theme-change", { detail: theme })
  );
}

export function toggleTheme(): Theme {
  const next = getTheme() === "light" ? "dark" : "light";
  setTheme(next);
  return next;
}

declare global {
  interface Window {
    fairdatahiveTheme?: {
      KEY: string;
      get: () => Theme;
      set: (theme: Theme) => void;
      toggle: () => Theme;
    };
  }
}
