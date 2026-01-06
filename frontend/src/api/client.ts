import type {
  AccessRequest,
  AccessStatus,
  CatalogStats,
  FairScore,
  LicenseInfo,
  PageModel,
  ResourceCreate,
  ResourceVersion,
  ResourceVersionSummary,
  SearchResponse,
  ThemeInfo,
  UploadResponse,
  UserProfile,
} from "../types";

const API_BASE =
  import.meta.env.VITE_API_BASE?.replace(/\/$/, "") || "/api/v1";

export class ApiClientError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.body = body;
  }
}

function getToken(): string | null {
  return localStorage.getItem("fairdatahive_token");
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = true
): Promise<T> {
  const headers = new Headers(options.headers);
  if (auth) {
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!res.ok) {
    const err = body as { detail?: string; message?: string };
    const msg =
      err?.detail || err?.message || `Request failed (${res.status})`;
    throw new ApiClientError(msg, res.status, body);
  }

  return body as T;
}

export const api = {
  health: () => request<{ status: string }>("/health", {}, false),

  search: (params: Record<string, string | number>) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== undefined) q.set(k, String(v));
    });
    return request<SearchResponse>(`/search?${q}`);
  },

  suggest: (q: string, scope?: string) => {
    const p = new URLSearchParams({ q });
    if (scope) p.set("scope", scope);
    return request<{ suggestions: string[] }>(`/search/suggest?${p}`, {}, false);
  },

  catalog: (scope?: string) => {
    const p = scope ? `?scope=${encodeURIComponent(scope)}` : "";
    return request<{ total: number; items: ResourceVersionSummary[] }>(
      `/catalog${p}`,
      {},
      false
    );
  },

  catalogStats: (scope?: string) => {
    const p = scope ? `?scope=${encodeURIComponent(scope)}` : "";
    return request<CatalogStats>(`/catalog/stats${p}`, {}, false);
  },

  licenses: () => request<LicenseInfo[]>("/licenses", {}, false),
  themes: () => request<ThemeInfo[]>("/themes", {}, false),

  listResources: (scope?: string, page = 1, size = 20) => {
    const p = new URLSearchParams({ page: String(page), size: String(size) });
    if (scope) p.set("scope", scope);
    return request<PageModel<ResourceVersionSummary>>(`/resources?${p}`, {}, false);
  },

  getResource: (versionId: string) =>
    request<ResourceVersion>(`/resources/${versionId}`, {}, false),

  listVersions: (baseId: string) =>
    request<ResourceVersionSummary[]>(`/resources/${baseId}/versions`, {}, false),

  createResource: (payload: ResourceCreate) =>
    request<ResourceVersion>("/resources", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  patchResource: (versionId: string, payload: Record<string, unknown>) =>
    request<ResourceVersion>(`/resources/${versionId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  publish: (versionId: string) =>
    request<ResourceVersion>(`/resources/${versionId}/publish`, {
      method: "POST",
    }),

  deleteResource: (baseId: string) =>
    request<void>(`/resources/${baseId}`, { method: "DELETE" }),

  fairScore: (versionId: string) =>
    request<FairScore>(`/resources/${versionId}/fair-score`, {}, false),

  uploadFile: (file: File, scope: string, resourceId?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    const p = new URLSearchParams({ scope });
    if (resourceId) p.set("resource_id", resourceId);
    return request<UploadResponse>(`/files/upload?${p}`, {
      method: "POST",
      body: fd,
    });
  },

  downloadUrl: (distributionId: string) =>
    request<{ download_url: string; expires_in: number }>(
      `/distributions/${distributionId}/download`,
      {},
      false
    ),

  accessStatus: (versionId: string) =>
    request<AccessStatus>(`/resources/${versionId}/access`, {}, false),

  createAccessRequest: (versionId: string, message?: string) =>
    request<AccessRequest>("/access-requests", {
      method: "POST",
      body: JSON.stringify({
        resource_version_id: versionId,
        message: message || null,
      }),
    }),

  incomingAccess: () => request<AccessRequest[]>("/access-requests/incoming"),

  outgoingAccess: () => request<AccessRequest[]>("/access-requests/outgoing"),

  acceptAccess: (id: string) =>
    request<AccessRequest>(`/access-requests/${id}/accept`, { method: "POST" }),

  rejectAccess: (id: string) =>
    request<AccessRequest>(`/access-requests/${id}/reject`, { method: "POST" }),

  me: () => request<UserProfile>("/users/me"),
  myResources: () => request<ResourceVersionSummary[]>("/users/me/resources"),

  landingUrl: (versionId: string) => `${API_BASE}/resources/${versionId}/landing`,
  turtleUrl: (versionId: string) => `${API_BASE}/resources/${versionId}.ttl`,
};
