import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { FacetSidebar } from "../components/FacetSidebar";
import { ResourceCard } from "../components/ResourceCard";
import { useScope } from "../context/ScopeContext";
import type { SearchResponse } from "../types";

type SearchMode = "auto" | "keyword" | "semantic";

export function SearchPage() {
  const { apiScope } = useScope();
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<SearchMode>("auto");
  const [theme, setTheme] = useState("");
  const [license, setLicense] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runSearch = useCallback(async () => {
    if (!q.trim()) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.search({
        q: q.trim(),
        mode,
        scope: apiScope,
        page,
        size: 20,
        ...(theme ? { theme } : {}),
        ...(license ? { license_id: license } : {}),
      });
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }, [q, mode, apiScope, page, theme, license]);

  useEffect(() => {
    const t = setTimeout(() => {
      if (q.trim()) runSearch();
    }, 400);
    return () => clearTimeout(t);
  }, [q, mode, apiScope, page, theme, license, runSearch]);

  return (
    <div className="page search-page">
      <header className="page-header">
        <h1>Search catalog</h1>
        <p className="subtitle">
          Keyword full-text or semantic search over published resources (
          <code>{apiScope}</code>).
        </p>
      </header>

      <form
        className="search-form"
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
          runSearch();
        }}
      >
        <input
          type="search"
          placeholder="Keywords or natural-language question…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          autoFocus
        />
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as SearchMode)}
        >
          <option value="auto">Auto</option>
          <option value="keyword">Keyword</option>
          <option value="semantic">Semantic</option>
        </select>
        <button type="submit" disabled={loading || !q.trim()}>
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {data && (
        <p className="search-meta">
          {data.total} results · mode: <strong>{data.mode_used}</strong>
        </p>
      )}

      {error && <div className="alert alert-error">{error}</div>}

      <div className="search-layout">
        {data && (
          <FacetSidebar
            facets={data.facets}
            themeFilter={theme}
            licenseFilter={license}
            onTheme={(v) => {
              setTheme(v);
              setPage(1);
            }}
            onLicense={(v) => {
              setLicense(v);
              setPage(1);
            }}
          />
        )}
        <div className="results-list">
          {!q.trim() && (
            <p className="empty-hint">
              Enter a query to search. Semantic mode works best with full
              questions.
            </p>
          )}
          {data?.results.map((hit) => (
            <ResourceCard
              key={hit.resource.id}
              resource={hit.resource}
              score={hit.score}
            />
          ))}
          {data && data.total > data.size && (
            <div className="pager">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </button>
              <span>
                Page {page} of {Math.ceil(data.total / data.size)}
              </span>
              <button
                type="button"
                disabled={page * data.size >= data.total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
