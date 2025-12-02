import { Link } from "react-router-dom";
import type { ResourceVersionSummary } from "../types";

interface Props {
  resource: ResourceVersionSummary;
  score?: number | null;
}

export function ResourceCard({ resource, score }: Props) {
  const fair =
    resource.fair_score != null
      ? Math.round(resource.fair_score * 100)
      : null;

  return (
    <article className="resource-card">
      <div className="card-head">
        <Link to={`/resources/${resource.id}`} className="card-title">
          {resource.title}
        </Link>
        <span className={`state state-${resource.state}`}>
          {resource.state}
        </span>
      </div>
      {resource.description && (
        <p className="card-desc">{truncate(resource.description, 180)}</p>
      )}
      <div className="card-meta">
        <span className="tag">{resource.theme}</span>
        {resource.license_id && (
          <span className="tag tag-muted">{resource.license_id}</span>
        )}
        {resource.is_private && <span className="tag tag-warn">Private</span>}
        {score != null && (
          <span className="tag tag-score">
            relevance {(score * 100).toFixed(0)}%
          </span>
        )}
        {fair != null && <span className="tag tag-fair">FAIR {fair}%</span>}
      </div>
      <div className="card-foot">
        <span>{formatDate(resource.issued)}</span>
        {resource.base_resource_id ? (
          <span className="mono">{resource.base_resource_id}</span>
        ) : null}
      </div>
    </article>
  );
}

function truncate(s: string, n: number) {
  return s.length <= n ? s : `${s.slice(0, n)}…`;
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}
