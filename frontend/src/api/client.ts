import axios, { type AxiosInstance, type AxiosRequestConfig } from "axios";
import type {
  AuthTokenPair,
  JobCreate,
  JobRead,
  JobRunRead,
  JobUpdate,
  MessageResponse,
  Page,
  ResultListParams,
  ResultRead,
  RunStartRequest,
  UserCreate,
  UserRead,
  UserUpdate,
} from "@/types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/";

const ACCESS_KEY = "crawler.access_token";
const REFRESH_KEY = "crawler.refresh_token";

/// <reference types="vite/client" />

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}
export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}
export function setTokens(t: AuthTokenPair): void {
  localStorage.setItem(ACCESS_KEY, t.access_token);
  localStorage.setItem(REFRESH_KEY, t.refresh_token);
}
export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

// Request: gắn Authorization
api.interceptors.request.use((cfg) => {
  const t = getAccessToken();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

// Response: refresh on 401 (queue) — auto-retry once.
let refreshPromise: Promise<AuthTokenPair> | null = null;

async function doRefresh(): Promise<AuthTokenPair> {
  const r = getRefreshToken();
  if (!r) throw new Error("no_refresh_token");
  const res = await axios.post<AuthTokenPair>(`${API_BASE}/auth/refresh`, { refresh_token: r }, {
    headers: { "Content-Type": "application/json" },
  });
  setTokens(res.data);
  return res.data;
}

api.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const original = error.config as AxiosRequestConfig & { _retry?: boolean };
    if (
      error.response?.status === 401 &&
      !original._retry &&
      !original.url?.includes("/auth/")
    ) {
      original._retry = true;
      try {
        if (!refreshPromise) refreshPromise = doRefresh().finally(() => (refreshPromise = null));
        const tok = await refreshPromise;
        original.headers = original.headers ?? {};
        (original.headers as Record<string, string>).Authorization = `Bearer ${tok.access_token}`;
        return api(original);
      } catch (e) {
        clearTokens();
        // Redirect to login
        if (typeof window !== "undefined") window.location.href = "/login";
        return Promise.reject(e);
      }
    }
    return Promise.reject(error);
  }
);

function errorMsg(e: unknown, fallback = "Lỗi không xác định"): string {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data as { detail?: unknown } | undefined;
    if (typeof d?.detail === "string") return d.detail;
    if (Array.isArray(d?.detail)) {
      return d.detail.map((x: { msg?: string }) => x.msg ?? "").filter(Boolean).join("; ");
    }
    return e.message;
  }
  if (e instanceof Error) return e.message;
  return fallback;
}

export { errorMsg };

// ============ AUTH ENDPOINTS ============
export const authApi = {
  login(email: string, password: string): Promise<AuthTokenPair> {
    return api.post("/auth/login", { email, password }).then((r) => r.data as AuthTokenPair);
  },
  signup(email: string, password: string, full_name?: string): Promise<AuthTokenPair> {
    return api.post("/auth/signup", { email, password, full_name }).then((r) => r.data as AuthTokenPair);
  },
  async refresh(): Promise<AuthTokenPair> {
    return (await api.post<AuthTokenPair>("/auth/refresh", { refresh_token: getRefreshToken() })).data;
  },
  logout() {
    return api.post("/auth/logout", { refresh_token: getRefreshToken() }).catch(() => null);
  },
  me(): Promise<UserRead> {
    return api.get("/auth/me").then((r) => r.data as UserRead);
  },
};

// ============ USERS (admin) ============
export const usersApi = {
  list(page = 1, size = 20): Promise<Page<UserRead>> {
    return api.get("/users", { params: { page, size } }).then((r) => r.data);
  },
  get(id: string): Promise<UserRead> {
    return api.get(`/users/${id}`).then((r) => r.data);
  },
  create(body: UserCreate): Promise<UserRead> {
    return api.post("/users", body).then((r) => r.data);
  },
  update(id: string, body: UserUpdate): Promise<UserRead> {
    return api.patch(`/users/${id}`, body).then((r) => r.data);
  },
  delete(id: string): Promise<void> {
    return api.delete(`/users/${id}`).then(() => undefined);
  },
};

// ============ JOBS ============
export const jobsApi = {
  list(params: { q?: string; status?: string; page?: number; size?: number } = {}): Promise<Page<JobRead>> {
    return api.get("/jobs", { params }).then((r) => r.data);
  },
  get(id: string): Promise<JobRead> {
    return api.get(`/jobs/${id}`).then((r) => r.data);
  },
  create(body: JobCreate): Promise<JobRead> {
    return api.post("/jobs", body).then((r) => r.data);
  },
  update(id: string, body: JobUpdate): Promise<JobRead> {
    return api.patch(`/jobs/${id}`, body).then((r) => r.data);
  },
  delete(id: string): Promise<void> {
    return api.delete(`/jobs/${id}`).then(() => undefined);
  },
};

// ============ RUNS ============
export const runsApi = {
  list(params: { job_id?: string; status?: string; page?: number; size?: number } = {}): Promise<Page<JobRunRead>> {
    return api.get("/runs", { params }).then((r) => r.data);
  },
  listForJob(jobId: string, params: { status?: string; page?: number; size?: number } = {}): Promise<Page<JobRunRead>> {
    return api.get(`/jobs/${jobId}/runs`, { params }).then((r) => r.data);
  },
  get(runId: string): Promise<JobRunRead> {
    return api.get(`/runs/${runId}`).then((r) => r.data);
  },
  start(jobId: string, body: RunStartRequest = {}): Promise<JobRunRead> {
    return api.post(`/jobs/${jobId}/runs`, body).then((r) => r.data);
  },
  cancel(runId: string): Promise<JobRunRead> {
    return api.post(`/runs/${runId}/cancel`).then((r) => r.data);
  },
  sseUrl(runId: string): string {
    const base = API_BASE.replace(/\/$/, "");
    return `${base}/runs/${runId}/events`;
  },
};

// ============ RESULTS ============
export const resultsApi = {
  list(params: ResultListParams): Promise<Page<ResultRead>> {
    return api.get("/results", { params }).then((r) => r.data);
  },
  exportCsvUrl(params: { job_id?: string; run_id?: string; q?: string; columns?: string[] }): string {
    const qs = new URLSearchParams();
    if (params.job_id) qs.set("job_id", params.job_id);
    if (params.run_id) qs.set("run_id", params.run_id);
    if (params.q) qs.set("q", params.q);
    if (params.columns?.length) qs.set("columns", params.columns.join(","));
    const base = API_BASE.replace(/\/$/, "");
    return `${base}/results/export.csv?${qs.toString()}`;
  },
  exportJsonUrl(params: { job_id?: string; run_id?: string; q?: string; columns?: string[] }): string {
    const qs = new URLSearchParams();
    if (params.job_id) qs.set("job_id", params.job_id);
    if (params.run_id) qs.set("run_id", params.run_id);
    if (params.q) qs.set("q", params.q);
    if (params.columns?.length) qs.set("columns", params.columns.join(","));
    const base = API_BASE.replace(/\/$/, "");
    return `${base}/results/export.json?${qs.toString()}`;
  },
};

export type { MessageResponse };