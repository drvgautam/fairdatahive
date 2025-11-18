import type { FairScore } from "../types";

function formatDimension(name: string) {
  return name.charAt(0).toUpperCase() + name.slice(1);
}

export function FairScorePanel({ fair }: { fair: FairScore }) {
  const pct = Math.round(fair.score * 100);

  return (
    <section className="fair-panel">
      <h3 className="fair-panel-title">
        <span>FAIR score</span>
        <strong>{pct}%</strong>
      </h3>
      <div className="fair-bar">
        <div className="fair-fill" style={{ width: `${pct}%` }} />
      </div>
      <ul className="fair-dims">
        {Object.entries(fair.dimensions).map(([name, dim]) => (
          <li key={name} className="fair-dim">
            <span className="dim-label">{formatDimension(name)}</span>
            <span className="dim-value">{Math.round(dim.score * 100)}%</span>
          </li>
        ))}
      </ul>
      {fair.suggestions.length > 0 && (
        <ul className="fair-suggestions">
          {fair.suggestions.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
