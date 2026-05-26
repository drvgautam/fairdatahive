export interface ResourceVersionSummary {
  id: string;
  base_resource_id?: string;
  title: string;
  description?: string;
  keywords: string[];
  theme: string;
  scope: string;
  state: string;
  is_current: boolean;
  is_private: boolean;
  license_id: string | null;
  doi: string | null;
  issued: string;
  modified: string;
  fair_score: number | null;
}

export interface Distribution {
  id: string;
  dist_type: string;
  title: string | null;
  description: string | null;
  access_url: string | null;
  download_url: string | null;
  media_type: string | null;
  checksum_sha256: string | null;
  byte_size: number | null;
  issued: string;
}

export interface Dataset {
  id: string;
  created_at: string;
  distributions: Distribution[];
}

export interface ResourceVersion extends ResourceVersionSummary {
  can_manage?: boolean;
  language: string | null;
  provenance: string | null;
  rights_statement: string | null;
  spatial: string | null;
  temporal: string | null;
  assumptions: string | null;
  technique: string | null;
  post_processing: string | null;
  access_rights: string[];
  publisher_sub: string;
  version_number: number;
  data_deleted: boolean;
  datasets: Dataset[];
}

export interface PageModel<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface FacetEntry {
  value: string;
  count: number;
}

export interface FacetGroup {
  themes: FacetEntry[];
  licenses: FacetEntry[];
  formats: FacetEntry[];
}

export interface SearchHit {
  resource: ResourceVersionSummary;
  score: number | null;
}

export interface SearchResponse {
  total: number;
  page: number;
  size: number;
  mode_used: "keyword" | "semantic" | "auto";
  results: SearchHit[];
  facets: FacetGroup;
}

export interface CatalogStats {
  total_resources: number;
  total_versions: number;
  total_published: number;
  total_drafts: number;
  total_distributions: number;
  by_theme: FacetEntry[];
  by_license: FacetEntry[];
}

export interface LicenseInfo {
  id: string;
  label: string;
  url: string;
  spdx: string;
}

export interface ThemeInfo {
  id: string;
  label: string;
}

export interface FairDimension {
  score: number;
  checks: Record<string, boolean>;
}

export interface FairScore {
  score: number;
  dimensions: Record<string, FairDimension>;
  suggestions: string[];
}

export interface UploadResponse {
  upload_token: string;
  object_key: string;
  checksum_sha256: string;
  byte_size: number;
  media_type: string | null;
  original_filename: string;
  extracted_files: UploadResponse[];
}

export interface DistributionCreate {
  dist_type: "upload" | "external" | "api";
  title?: string;
  description?: string;
  upload_token?: string;
  access_url?: string;
  media_type?: string;
  checksum_sha256?: string;
  byte_size?: number;
  data_service?: { endpoint_url: string; description?: string };
}

export interface ResourceCreate {
  scope: string;
  title: string;
  description: string;
  keywords: string[];
  theme: string;
  license_id?: string;
  language?: string;
  provenance?: string;
  is_private?: boolean;
  datasets: { distributions: DistributionCreate[] }[];
}

export interface AccessRequest {
  id: string;
  resource_version_id: string;
  requester_sub: string;
  status: string;
  message: string | null;
  created_at: string;
}

export interface AccessStatus {
  is_private: boolean;
  can_download: boolean;
  pending_request: boolean;
  access_rights: string[];
}

export interface UserProfile {
  sub: string;
  display_name: string | null;
  email: string | null;
}

export interface ApiError {
  detail?: string;
  message?: string;
  error_code?: string;
}
