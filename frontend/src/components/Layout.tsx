import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useScope } from "../context/ScopeContext";
import { Logo } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";

export function Layout() {
  const { token, setToken, profile } = useAuth();
  const { mode, projectId, setMode, setProjectId } = useScope();

  return (
    <div className="app-shell">
      <header className="top-bar">
        <Link to="/" className="brand">
          <span className="brand-mark">
            <Logo size="100%" />
          </span>
          <span className="brand-text">FairDataHive</span>
        </Link>

        <nav className="main-nav">
          <NavLink to="/search">Search</NavLink>
          <NavLink to="/catalog">Catalog</NavLink>
          <NavLink to="/create">Create</NavLink>
          <NavLink to="/my">My resources</NavLink>
          <NavLink to="/access">Access</NavLink>
          <NavLink to="/about">About</NavLink>
        </nav>

        <div className="scope-bar">
          <label>
            Scope
            <select
              value={mode}
              onChange={(e) =>
                setMode(e.target.value as "public" | "project")
              }
            >
              <option value="public">Public catalog</option>
              <option value="project">Project</option>
            </select>
          </label>
          {mode === "project" && (
            <input
              type="text"
              placeholder="Project ID"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="project-input"
            />
          )}
        </div>

        <ThemeToggle />

        <div className="auth-bar">
          {profile ? (
            <span className="user-chip" title={profile.sub}>
              {profile.display_name || profile.sub}
            </span>
          ) : null}
          <input
            type="password"
            className="token-input"
            placeholder="Bearer token"
            value={token || ""}
            onChange={(e) => setToken(e.target.value || null)}
            title="JWT or 'dev' when DEV_AUTH_ENABLED"
          />
        </div>
      </header>

      <main className="page-content">
        <Outlet />
      </main>

      <footer className="site-footer">
        <span>DCAT-AP · FAIR · OAI-PMH</span>
        <a href="/docs" target="_blank" rel="noreferrer">
          Docs
        </a>
      </footer>
    </div>
  );
}
