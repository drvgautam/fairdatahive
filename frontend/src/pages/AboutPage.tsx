export function AboutPage() {
  return (
    <div className="page about-page">
      <header className="page-header">
        <h1>About FairDataHive</h1>
        <p className="subtitle">
          A research data catalog designed for discoverability, interoperability,
          and responsible data sharing.
        </p>
      </header>

      <section className="prose">
        <p>
          FairDataHive helps research teams register, describe, version, and publish
          datasets in a structured catalog. Metadata is stored in a relational
          database, files are held in object storage, and the system exposes
          machine-readable exports so records can be discovered by humans and by
          external harvesters alike.
        </p>

        <h2>Standards and principles</h2>
        <p>
          The footer labels <strong>DCAT-AP</strong>, <strong>FAIR</strong>, and{" "}
          <strong>OAI-PMH</strong> refer to the main interoperability frameworks
          supported by this application. Together they define how data are
          described, how quality is assessed, and how metadata can be collected
          by other services.
        </p>

        <h3>DCAT and DCAT-AP</h3>
        <p>
          The W3C <strong>Data Catalog Vocabulary (DCAT)</strong> provides a
          standard way to describe catalogs, datasets, and distributions (files
          or access points). <strong>DCAT-AP</strong> (DCAT Application Profile)
          is the European application profile: it refines DCAT with recommended
          fields and constraints commonly used in public-sector and research
          data portals.
        </p>
        <p>
          In FairDataHive, each published record is modelled as a DCAT resource with
          one or more versions. Each version may include distributions (uploaded
          files, external URLs, or API endpoints). The API can export catalog and
          resource metadata as Turtle or JSON-LD, and optional SHACL validation
          helps check records against DCAT-AP-style rules before or after
          publication.
        </p>

        <h3>FAIR data principles</h3>
        <p>
          <strong>FAIR</strong> stands for <em>Findable</em>, <em>Accessible</em>
          , <em>Interoperable</em>, and <em>Reusable</em>. These principles guide
          how research data and metadata should be managed so that others can
          locate, understand, and reuse them with appropriate controls.
        </p>
        <p>
          FairDataHive computes a FAIR score for each resource version across these
          four dimensions, with concrete checks (for example: persistent
          identifiers, licence, publisher, and distribution availability) and
          suggestions for improvement. A minimum FAIR score is required before a
          draft can be published, encouraging complete and well-documented
          entries.
        </p>

        <h3>OAI-PMH harvesting</h3>
        <p>
          The <strong>Open Archives Initiative Protocol for Metadata Harvesting
          (OAI-PMH)</strong> is a widely used protocol that allows external
          systems to list and retrieve metadata records from a repository in a
          standard way. FairDataHive exposes an OAI-PMH endpoint so catalog metadata
          can be harvested into national portals, institutional repositories, or
          federated search services without custom integration for each record.
        </p>

        <h2>Catalog structure</h2>
        <p>
          The internal model follows DCAT concepts, expressed in plain language
          as follows:
        </p>
        <ul>
          <li>
            <strong>Catalog</strong> — the collection of published resources
            visible in a given scope.
          </li>
          <li>
            <strong>Resource</strong> — a logical dataset (identified by a
            stable base ID) that may evolve over time.
          </li>
          <li>
            <strong>Version</strong> — a snapshot of metadata and files at a
            point in time (draft, published, or deprecated).
          </li>
          <li>
            <strong>Distribution</strong> — a concrete way to obtain the data
            (file upload, external link, or data service URL).
          </li>
        </ul>

        <h2>Catalog scopes</h2>
        <p>
          Resources are tagged with a <strong>scope</strong> that controls where
          they appear in browse and search results:
        </p>
        <ul>
          <li>
            <strong>public</strong> — entries intended for the open catalog,
            discoverable by all users.
          </li>
          <li>
            <strong>project</strong> — entries associated with a consortium or
            project identifier, useful for team workspaces alongside the public
            catalog.
          </li>
        </ul>
        <p>
          Use the scope selector in the header to switch between the public
          catalog and a project view before searching or creating records.
        </p>

        <h2>Discovery and search</h2>
        <p>
          The search interface supports multiple modes so users can locate
          relevant material efficiently:
        </p>
        <ul>
          <li>
            <strong>Keyword</strong> — full-text search over titles and
            descriptions (PostgreSQL text search), ranked by relevance.
          </li>
          <li>
            <strong>Semantic</strong> — natural-language queries matched via
            vector embeddings stored in the database (pgvector).
          </li>
          <li>
            <strong>Auto</strong> — combines keyword results with semantic
            search when keyword matches are sparse.
          </li>
        </ul>
        <p>
          Facets for theme, licence, and format help narrow results within the
          active scope.
        </p>

        <h2>Access and governance</h2>
        <p>
          Resources may be published as open or marked <strong>private</strong>.
          Private distributions require authentication; users without direct
          access may submit an access request to the resource owner. Owners can
          accept or reject requests, which updates download rights on the
          record. This model supports controlled sharing within a FAIR framework
          without exposing sensitive files publicly.
        </p>

        <h2>Further information</h2>
        <p>
          For setup and API reference, use the <strong>Docs</strong> link in the
          page footer (project guide; Swagger at <code>/swagger</code>). Published resources also offer
          per-record landing pages, RDF downloads, and download links for
          distributions where access is permitted.
        </p>
      </section>
    </div>
  );
}
