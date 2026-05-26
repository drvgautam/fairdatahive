import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { FairScorePanel } from "../components/FairScorePanel";
import { useAuth } from "../context/AuthContext";
import type {
  AccessStatus,
  FairScore,
  ResourceVersion,
  ResourceVersionSummary,
} from "../types";

export function ResourcePage() {
  const { versionId } = useParams<{ versionId: string }>();
  const navigate = useNavigate();
  const { token, profile } = useAuth();
  const [resource, setResource] = useState<ResourceVersion | null>(null);
  const [versions, setVersions] = useState<ResourceVersionSummary[]>([]);
  const [fair, setFair] = useState<FairScore | null>(null);
  const [access, setAccess] = useState<AccessStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!versionId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const r = await api.getResource(versionId);
        if (cancelled) return;
        setResource(r);
        const [vlist, f, a] = await Promise.all([
          api.listVersions(r.base_resource_id!),
          api.fairScore(versionId),
          api.accessStatus(versionId),
        ]);
        if (!cancelled) {
          setVersions(vlist);
          setFair(f);
          setAccess(a);
        }
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
  }, [versionId]);

  async function publish() {
    if (!versionId) return;
    setBusy(true);
    setActionMsg(null);
    try {
      const r = await api.publish(versionId);
      setResource(r);
      setActionMsg("Published successfully.");
      setFair(await api.fairScore(versionId));
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : "Publish failed");
    } finally {
      setBusy(false);
    }
  }

  async function requestAccess() {
    if (!versionId) return;
    setBusy(true);
    try {
      await api.createAccessRequest(versionId, "Access requested via UI");
      setAccess(await api.accessStatus(versionId));
      setActionMsg("Access request submitted.");
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  async function download(distId: string) {
    try {
      const { download_url } = await api.downloadUrl(distId);
      window.open(download_url, "_blank");
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : "Download failed");
    }
  }

  const isOwner =
    Boolean(token) &&
    Boolean(profile?.sub) &&
    profile?.sub === resource?.publisher_sub;

  async function deleteResource() {
    if (!resource?.base_resource_id) return;
    const label =
      resource.state === "draft"
        ? "Delete this draft permanently?"
        : "Delete this resource? Metadata will be kept as a tombstone; files will be removed from storage.";
    if (!window.confirm(label)) return;

    setBusy(true);
    setActionMsg(null);
    try {
      if (resource.state === "draft") {
        await api.deleteVersion(resource.id);
      } else {
        await api.deleteResource(resource.base_resource_id);
      }
      navigate("/my", { replace: true });
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="loading">Loading resource…</p>;
  if (error) return <div className="alert alert-error">{error}</div>;
  if (!resource) return null;

  return (
    <div className="page resource-page">
      <header className="page-header">
        <div className="resource-head">
          <h1>{resource.title}</h1>
          <span className={`state state-${resource.state}`}>
            {resource.state}
          </span>
        </div>
        <p className="subtitle mono">{resource.id}</p>
      </header>

      {actionMsg && <div className="alert">{actionMsg}</div>}

      <div className="resource-layout">
        <div className="resource-main">
          <section>
            <h2>Description</h2>
            <p>{resource.description}</p>
          </section>

          <section className="meta-grid">
            <Meta label="Theme" value={resource.theme} />
            <Meta label="Scope" value={resource.scope} />
            <Meta label="License" value={resource.license_id || "—"} />
            <Meta label="DOI" value={resource.doi || "—"} />
            <Meta label="Keywords" value={resource.keywords.join(", ")} />
            <Meta label="Issued" value={formatDate(resource.issued)} />
          </section>

          <section>
            <h2>Distributions</h2>
            {resource.datasets.flatMap((ds) =>
              ds.distributions.map((d) => (
                <div key={d.id} className="dist-row">
                  <span className="tag">{d.dist_type}</span>
                  <span>{d.title || d.media_type || d.id}</span>
                  {d.byte_size != null && (
                    <span className="muted">
                      {(d.byte_size / 1024).toFixed(1)} KB
                    </span>
                  )}
                  {(d.dist_type === "upload" ||
                    d.access_url ||
                    d.download_url) && (
                    <button type="button" onClick={() => download(d.id)}>
                      Download
                    </button>
                  )}
                </div>
              ))
            )}
          </section>

          {access?.is_private && !access.can_download && token && (
            <section>
              <button type="button" onClick={requestAccess} disabled={busy}>
                Request access
              </button>
            </section>
          )}

          <section className="resource-links">
            <h2>Export &amp; links</h2>
            <nav className="resource-links-nav" aria-label="Resource export links">
              <a
                href={api.landingUrl(resource.id)}
                target="_blank"
                rel="noreferrer"
              >
                Landing page
              </a>
              <a
                href={api.turtleUrl(resource.id)}
                target="_blank"
                rel="noreferrer"
              >
                RDF (Turtle)
              </a>
            </nav>
          </section>

          {isOwner && !resource.data_deleted && (
            <section className="resource-actions">
              {resource.state === "draft" && (
                <button type="button" onClick={publish} disabled={busy}>
                  Publish
                </button>
              )}
              <button
                type="button"
                className="btn-danger"
                onClick={deleteResource}
                disabled={busy}
              >
                {resource.state === "draft" ? "Delete draft" : "Delete resource"}
              </button>
            </section>
          )}
          {resource.data_deleted && (
            <section className="alert alert-error">
              This resource has been deleted. Only metadata is retained.
            </section>
          )}
        </div>

        <aside className="resource-aside">
          {fair && <FairScorePanel fair={fair} />}
          <section>
            <h3>Versions</h3>
            <ul className="version-list">
              {versions.map((v) => (
                <li key={v.id}>
                  <Link
                    to={`/resources/${v.id}`}
                    className={v.id === resource.id ? "active" : ""}
                  >
                    {v.id.slice(-12)} — {v.state}
                    {v.is_current && " (current)"}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="meta-label">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}
