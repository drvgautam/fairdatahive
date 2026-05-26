import { useCallback, useEffect, useState } from "react";
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
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadItems = useCallback(async () => {
    const list = await api.myResources();
    setItems(list);
  }, []);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        await loadItems();
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
  }, [token, loadItems]);

  async function handleDelete(r: ResourceVersionSummary) {
    const baseId = r.base_resource_id;
    if (!baseId) return;
    const label =
      r.state === "draft"
        ? `Delete draft "${r.title}" permanently?`
        : `Delete "${r.title}"? Files will be removed; metadata is kept as a tombstone.`;
    if (!window.confirm(label)) return;

    setDeletingId(r.id);
    setActionMsg(null);
    try {
      if (r.state === "draft") {
        await api.deleteVersion(r.id);
      } else {
        await api.deleteResource(baseId);
      }
      await loadItems();
      setActionMsg(`Deleted "${r.title}".`);
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  }

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
      {actionMsg && <div className="alert">{actionMsg}</div>}

      <div className="results-list">
        {items.map((r) => (
          <div key={r.id} className="my-resource-row">
            <ResourceCard resource={r} />
            <button
              type="button"
              className="btn-danger btn-sm"
              disabled={deletingId === r.id}
              onClick={() => handleDelete(r)}
            >
              {deletingId === r.id ? "Deleting…" : "Delete"}
            </button>
          </div>
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
