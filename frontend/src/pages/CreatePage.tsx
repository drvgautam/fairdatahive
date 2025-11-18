import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useScope } from "../context/ScopeContext";
import type {
  DistributionCreate,
  LicenseInfo,
  ThemeInfo,
  UploadResponse,
} from "../types";

interface PendingFile {
  file: File;
  upload?: UploadResponse;
  uploading?: boolean;
  error?: string;
}

export function CreatePage() {
  const navigate = useNavigate();
  const { apiScope } = useScope();

  const [licenses, setLicenses] = useState<LicenseInfo[]>([]);
  const [themes, setThemes] = useState<ThemeInfo[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [keywords, setKeywords] = useState("");
  const [theme, setTheme] = useState("");
  const [licenseId, setLicenseId] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [files, setFiles] = useState<PendingFile[]>([]);
  const [externalUrl, setExternalUrl] = useState("");
  const [apiUrl, setApiUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [publishAfter, setPublishAfter] = useState(false);

  useEffect(() => {
    Promise.all([api.licenses(), api.themes()]).then(([l, t]) => {
      setLicenses(l);
      setThemes(t);
      if (t.length) setTheme(t[0].id);
      if (l.length) setLicenseId(l[0].id);
    });
  }, []);

  async function handleFileSelect(list: FileList | null) {
    if (!list) return;
    const added: PendingFile[] = Array.from(list).map((file) => ({ file }));
    setFiles((prev) => [...prev, ...added]);

    for (const entry of added) {
      setFiles((prev) =>
        prev.map((p) =>
          p.file === entry.file ? { ...p, uploading: true } : p
        )
      );
      try {
        const upload = await api.uploadFile(entry.file, apiScope);
        setFiles((prev) =>
          prev.map((p) =>
            p.file === entry.file ? { ...p, upload, uploading: false } : p
          )
        );
      } catch (e) {
        setFiles((prev) =>
          prev.map((p) =>
            p.file === entry.file
              ? {
                  ...p,
                  uploading: false,
                  error: e instanceof Error ? e.message : "Upload failed",
                }
              : p
          )
        );
      }
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const kw = keywords
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);
    if (kw.length < 2) {
      setError("At least 2 keywords required (comma-separated).");
      return;
    }
    if (description.length < 50) {
      setError("Description must be at least 50 characters.");
      return;
    }

    const distributions: DistributionCreate[] = [];

    for (const f of files) {
      if (!f.upload) {
        setError("Wait for all file uploads to finish.");
        return;
      }
      const extracted = f.upload.extracted_files ?? [];
      if (extracted.length > 0) {
        for (const ex of extracted) {
          if (!ex.upload_token?.trim()) {
            setError(
              `Missing upload token for extracted file "${ex.original_filename}".`
            );
            return;
          }
          distributions.push({
            dist_type: "upload",
            title: ex.original_filename,
            upload_token: ex.upload_token,
            media_type: ex.media_type || undefined,
            checksum_sha256: ex.checksum_sha256,
            byte_size: ex.byte_size,
          });
        }
      } else {
        if (!f.upload.upload_token?.trim()) {
          setError(`Missing upload token for "${f.upload.original_filename}".`);
          return;
        }
        distributions.push({
          dist_type: "upload",
          title: f.upload.original_filename,
          upload_token: f.upload.upload_token,
          media_type: f.upload.media_type || undefined,
          checksum_sha256: f.upload.checksum_sha256,
          byte_size: f.upload.byte_size,
        });
      }
    }

    if (externalUrl.trim()) {
      distributions.push({
        dist_type: "external",
        title: "External link",
        access_url: externalUrl.trim(),
      });
    }

    if (apiUrl.trim()) {
      distributions.push({
        dist_type: "api",
        title: "API endpoint",
        access_url: apiUrl.trim(),
        data_service: { endpoint_url: apiUrl.trim() },
      });
    }

    setSubmitting(true);
    try {
      const created = await api.createResource({
        scope: apiScope,
        title: title.trim(),
        description: description.trim(),
        keywords: kw,
        theme,
        license_id: licenseId || undefined,
        is_private: isPrivate,
        datasets: [{ distributions }],
      });

      let version = created;
      if (publishAfter && created.state === "draft") {
        version = await api.publish(created.id);
      }
      navigate(`/resources/${version.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page create-page">
      <header className="page-header">
        <h1>Create resource</h1>
        <p className="subtitle">
          Draft a new DCAT dataset in scope <code>{apiScope}</code>. Upload
          files first, then save metadata.
        </p>
      </header>

      {error && <div className="alert alert-error">{error}</div>}

      <form className="create-form" onSubmit={handleSubmit}>
        <section>
          <h2>Metadata</h2>
          <label>
            Title
            <input
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label>
            Description (min 50 chars)
            <textarea
              required
              rows={5}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <span className="hint">{description.length} / 50+</span>
          </label>
          <label>
            Keywords (comma-separated, min 2)
            <input
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="electrochemistry, coating, corrosion"
            />
          </label>
          <div className="row-2">
            <label>
              Theme
              <select value={theme} onChange={(e) => setTheme(e.target.value)}>
                {themes.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              License
              <select
                value={licenseId}
                onChange={(e) => setLicenseId(e.target.value)}
              >
                {licenses.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={isPrivate}
              onChange={(e) => setIsPrivate(e.target.checked)}
            />
            Private resource (access requests required)
          </label>
        </section>

        <section>
          <h2>Distributions</h2>
          <label>
            Upload files
            <input
              type="file"
              multiple
              onChange={(e) => handleFileSelect(e.target.files)}
            />
          </label>
          <ul className="upload-list">
            {files.map((f, i) => {
              const extracted = f.upload?.extracted_files ?? [];
              return (
                <li key={i}>
                  {f.file.name}
                  {f.uploading && " — uploading…"}
                  {f.upload &&
                    extracted.length === 0 &&
                    ` — ${(f.upload.byte_size / 1024).toFixed(1)} KB`}
                  {f.upload &&
                    extracted.length > 0 &&
                    ` — ${extracted.length} file(s) extracted`}
                  {f.error && <span className="err"> {f.error}</span>}
                  {extracted.length > 0 && (
                    <ul>
                      {extracted.map((ex, j) => (
                        <li key={j}>{ex.original_filename}</li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
          <label>
            External URL
            <input
              type="url"
              value={externalUrl}
              onChange={(e) => setExternalUrl(e.target.value)}
              placeholder="https://…"
            />
          </label>
          <label>
            API / data service URL
            <input
              type="url"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="https://api.example.com/data"
            />
          </label>
        </section>

        <section className="form-actions">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={publishAfter}
              onChange={(e) => setPublishAfter(e.target.checked)}
            />
            Publish immediately (requires license + FAIR threshold + distribution)
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? "Saving…" : "Create draft"}
          </button>
        </section>
      </form>
    </div>
  );
}
