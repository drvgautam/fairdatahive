import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ResourceCard } from "../components/ResourceCard";
import { useAuth } from "../context/AuthContext";
import type { ResourceVersionSummary } from "../types";

export function MyResourcesPage() {
  const { token } = useAuth();
  const [items, setItems] = useState<ResourceVersionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const list = await api.myResources();
        if (!cancelled) setItems(list);
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (!token) {
    return (
      <div className="page">
        <div className="alert">
          Set a bearer token in the header (or enable dev auth) to view your
          resources.
        </div>
        <Link to="/create">Create a resource</Link>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>My resources</h1>
        <p className="subtitle">Drafts and published records you own.</p>
      </header>

      {loading && <p className="loading">Loading…</p>}
      {error && <div className="alert alert-error">{error}</div>}

      <div className="results-list">
        {items.map((r) => (
          <ResourceCard key={r.id} resource={r} />
        ))}
        {!loading && items.length === 0 && (
          <p className="empty-hint">
            No resources yet. <Link to="/create">Create one</Link>.
          </p>
        )}
      </div>
    </div>
  );
}
