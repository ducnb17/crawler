export interface AuthTokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserRead {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  scopes: string[];
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  email: string;
  password: string;
  full_name?: string | null;
  scopes?: string[];
  is_superuser?: boolean;
}

export interface UserUpdate {
  full_name?: string | null;
  is_active?: boolean;
  scopes?: string[];
}

export interface JobRead {
  id: string;
  owner_id: string | null;
  name: string;
  description: string | null;
  start_urls: string[];
  allowed_domains: string[];
  item_container: string | null;
  fields: Record<string, FieldSpec>;
  next_page: string | null;
  follow_links: boolean;
  max_pages: number;
  max_depth: number;
  delay: number;
  render_js: boolean;
  robots_obey: boolean;
  concurrency: number;
  schedule_cron: string | null;
  is_active: boolean;
  allow_concurrent_runs: boolean;
  proxy_profile_id: string | null;
  webhook_id: string | null;
  llm_detect_config: Record<string, unknown>;
  status: string;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobCreate {
  name: string;
  description?: string | null;
  start_urls: string[];
  allowed_domains: string[];
  item_container?: string | null;
  fields: Record<string, FieldSpec>;
  next_page?: string | null;
  follow_links?: boolean;
  max_pages?: number;
  max_depth?: number;
  delay?: number;
  render_js?: boolean;
  robots_obey?: boolean;
  concurrency?: number;
  schedule_cron?: string | null;
  is_active?: boolean;
  allow_concurrent_runs?: boolean;
  proxy_profile_id?: string | null;
  webhook_id?: string | null;
  llm_detect_config?: Record<string, unknown>;
}

export type JobUpdate = Partial<JobCreate>;

export interface FieldSpec {
  selector: string;
  attr?: string | null;
  type?: "text" | "attr" | "html" | "regex" | "jsonld";
  regex?: string | null;
  transform?: "strip" | "lower" | "upper" | "int" | "float" | "price" | null;
}

export interface JobRunRead {
  id: string;
  job_id: string;
  status: "pending" | "running" | "done" | "failed" | "cancelled";
  triggered_by: string;
  started_at: string | null;
  ended_at: string | null;
  pages_crawled: number;
  pages_failed: number;
  items_extracted: number;
  error: string | null;
  return_code: number | null;
  stats: Record<string, unknown>;
  created_at: string;
}

export interface RunStartRequest {
  triggered_by?: string;
  allow_concurrent?: boolean;
}

export interface ResultRead {
  id: string;
  job_id: string;
  run_id: string | null;
  url: string;
  content_hash: string | null;
  data: Record<string, unknown>;
  extracted_at: string;
}

export interface Page<T> {
  items: T[];
  page: number;
  size: number;
  total: number;
  pages: number;
}

export interface ResultListParams {
  q?: string;
  job_id?: string;
  run_id?: string;
  url_contains?: string;
  page?: number;
  size?: number;
  sort?: string;
}

export interface MessageResponse {
  message: string;
  detail?: string;
}

/** SSE event emitted from /runs/{id}/events */
export type RunEvent =
  | { event: "start"; ts: string; run_id: string; job_id: string }
  | { event: "page_done"; ts: string; url: string; depth: number; status: number; items: number; elapsed_ms: number; fallback?: string }
  | { event: "page_failed"; ts: string; url?: string; status?: number; error?: string }
  | { event: "progress"; ts: string; pages_crawled: number; items: number }
  | { event: "done"; ts: string; pages_crawled: number; pages_failed: number; items_extracted: number; fallbacks_playwright: number; fallbacks_cloudscraper: number }
  | { event: "error"; ts: string; error: string }
  | { event: "ping" };