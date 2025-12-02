import type { FacetGroup } from "../types";

interface Props {
  facets: FacetGroup;
  themeFilter: string;
  licenseFilter: string;
  onTheme: (v: string) => void;
  onLicense: (v: string) => void;
}

export function FacetSidebar({
  facets,
  themeFilter,
  licenseFilter,
  onTheme,
  onLicense,
}: Props) {
  return (
    <aside className="facet-sidebar">
      <h3>Refine</h3>
      <FacetList
        label="Themes"
        entries={facets.themes}
        active={themeFilter}
        onSelect={onTheme}
      />
      <FacetList
        label="Licenses"
        entries={facets.licenses}
        active={licenseFilter}
        onSelect={onLicense}
      />
      {facets.formats.length > 0 && (
        <div className="facet-group">
          <h4>Formats</h4>
          <ul>
            {facets.formats.map((f) => (
              <li key={f.value}>
                {f.value} ({f.count})
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}

function FacetList({
  label,
  entries,
  active,
  onSelect,
}: {
  label: string;
  entries: { value: string; count: number }[];
  active: string;
  onSelect: (v: string) => void;
}) {
  if (!entries.length) return null;
  return (
    <div className="facet-group">
      <h4>{label}</h4>
      <ul>
        <li>
          <button
            type="button"
            className={!active ? "facet-active" : ""}
            onClick={() => onSelect("")}
          >
            All
          </button>
        </li>
        {entries.map((e) => (
          <li key={e.value}>
            <button
              type="button"
              className={active === e.value ? "facet-active" : ""}
              onClick={() => onSelect(e.value)}
            >
              {e.value} ({e.count})
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
