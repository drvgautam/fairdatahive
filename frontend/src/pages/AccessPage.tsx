import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { AccessRequest } from "../types";

export function AccessPage() {
  const { token } = useAuth();
  const [incoming, setIncoming] = useState<AccessRequest[]>([]);
  const [outgoing, setOutgoing] = useState<AccessRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [inc, out] = await Promise.all([
        api.incomingAccess(),
        api.outgoingAccess(),
      ]);
      setIncoming(inc);
      setOutgoing(out);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) load();
    else setLoading(false);
  }, [token]);

  async function accept(id: string) {
    await api.acceptAccess(id);
    await load();
  }

  async function reject(id: string) {
    await api.rejectAccess(id);
    await load();
  }

  if (!token) {
    return (
      <div className="page access-page">
        <div className="alert">Authentication required for access requests.</div>
      </div>
    );
  }

  return (
    <div className="page access-page">
      <header className="page-header">
        <h1>Access requests</h1>
        <p className="subtitle">Manage private resource download rights.</p>
      </header>

      {loading && <p className="loading">Loading…</p>}
      {error && <div className="alert alert-error">{error}</div>}

      <section>
        <h2>Incoming (for your resources)</h2>
        <RequestTable
          items={incoming}
          onAccept={accept}
          onReject={reject}
          showActions
        />
      </section>

      <section>
        <h2>Outgoing (your requests)</h2>
        <RequestTable items={outgoing} />
      </section>
    </div>
  );
}

function RequestTable({
  items,
  onAccept,
  onReject,
  showActions,
}: {
  items: AccessRequest[];
  onAccept?: (id: string) => void;
  onReject?: (id: string) => void;
  showActions?: boolean;
}) {
  if (!items.length) return <p className="empty-hint">None.</p>;
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Resource</th>
          <th>Requester</th>
          <th>Status</th>
          <th>Date</th>
          {showActions && <th>Actions</th>}
        </tr>
      </thead>
      <tbody>
        {items.map((r) => (
          <tr key={r.id}>
            <td>
              <Link to={`/resources/${r.resource_version_id}`}>
                {r.resource_version_id.slice(0, 24)}…
              </Link>
            </td>
            <td className="mono">{r.requester_sub}</td>
            <td>
              <span className={`state state-${r.status}`}>{r.status}</span>
            </td>
            <td>{new Date(r.created_at).toLocaleDateString()}</td>
            {showActions && onAccept && onReject && (
              <td>
                {r.status === "pending" && (
                  <>
                    <button type="button" onClick={() => onAccept(r.id)}>
                      Accept
                    </button>
                    <button
                      type="button"
                      className="btn-muted"
                      onClick={() => onReject(r.id)}
                    >
                      Reject
                    </button>
                  </>
                )}
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
