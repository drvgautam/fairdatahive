import { useTheme } from "../context/ThemeContext";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isLight = theme === "light";

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggleTheme}
      aria-pressed={isLight}
      title={isLight ? "Switch to dark mode" : "Switch to light mode"}
    >
      <span className="theme-toggle-icon" aria-hidden="true">
        {isLight ? "☀" : "☽"}
      </span>
      <span className="theme-toggle-label">{isLight ? "Dark" : "Light"}</span>
    </button>
  );
}
