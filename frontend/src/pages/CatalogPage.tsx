import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ResourceCard } from "../components/ResourceCard";
import { useScope } from "../context/ScopeContext";
import type { CatalogStats, ResourceVersionSummary } from "../types";

export function CatalogPage() {
  const { projectId: routeProject } = useParams();
  const { apiScope, mode, projectId } = useScope();
  const scope = routeProject || apiScope;

  const [items, setItems] = useState<ResourceVersionSummary[]>([]);
  const [stats, setStats] = useState<CatalogStats | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [list, st] = await Promise.all([
          api.catalog(scope),
          api.catalogStats(),
        ]);
        if (!cancelled) {
          setItems(
            list.items.map((i) => ({
              ...i,
              state: "published",
              keywords: [],
              scope: scope,
              is_current: true,
              is_private: false,
              modified: i.issued,
              fair_score: null,
            }))
          );
          setTotal(list.total);
          setStats(st);
        }
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Failed to load catalog");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [scope]);

  const title =
    routeProject || (mode === "project" && projectId)
      ? `Project: ${scope}`
      : "Public catalog";

  return (
    <div className="page catalog-page">
      <header className="page-header">
        <h1>{title}</h1>
        <p className="subtitle">
          Browse published DCAT resources.{" "}
          {mode === "project" && !routeProject && (
            <Link to={`/projects/${encodeURIComponent(projectId)}`}>
              Permalink
            </Link>
          )}
        </p>
      </header>

      {stats && (
        <div className="stats-grid">
          <Stat label="Resources" value={stats.total_resources} />
          <Stat label="Published" value={stats.total_published} />
          <Stat label="Drafts" value={stats.total_drafts} />
          <Stat label="Distributions" value={stats.total_distributions} />
        </div>
      )}

      {loading && <p className="loading">Loading catalog…</p>}
      {error && <div className="alert alert-error">{error}</div>}

      <div className="results-list">
        {items.map((r) => (
          <ResourceCard key={r.id} resource={r} />
        ))}
      </div>

      {total > items.length && (
        <p className="hint">
          Showing {items.length} of {total} resources. Use Search for full
          discovery.
        </p>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat-card">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}
