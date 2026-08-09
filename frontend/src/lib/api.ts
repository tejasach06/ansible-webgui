export interface ApiError extends Error { code?: string; status?: number; detail?: Record<string, unknown>; }
let refreshInFlight: Promise<boolean> | null = null;
async function refreshSession(): Promise<boolean> {
  refreshInFlight ??= fetch("/api/auth/refresh", { method: "POST", credentials: "include", headers: { "X-Requested-With": "XMLHttpRequest" } })
    .then((response) => response.ok)
    .finally(() => { refreshInFlight = null; });
  return refreshInFlight;
}
export async function apiFetch<T = unknown>(endpoint: string, options: RequestInit = {}, retried = false): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body && typeof options.body === "string") headers.set("Content-Type", "application/json");
  const method = options.method?.toUpperCase() || "GET";
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) headers.set("X-Requested-With", "XMLHttpRequest");
  const response = await fetch(endpoint, { ...options, headers, credentials: "include" });
  if (response.status === 401 && !retried && endpoint !== "/api/auth/login" && endpoint !== "/api/auth/refresh" && await refreshSession()) return apiFetch<T>(endpoint, options, true);
  if (!response.ok) {
    let errData: { detail?: { code?: string; message?: string } } = {};
    try { errData = await response.json(); } catch { /* Ignore parse failure */ }
    const detail = errData.detail || {};
    const error: ApiError = new Error(detail.message || response.statusText);
    error.code = detail.code || "unknown_error"; error.status = response.status; error.detail = detail as Record<string, unknown>;
    throw error;
  }
  if (response.status === 204) return {} as T;
  return response.json();
}
