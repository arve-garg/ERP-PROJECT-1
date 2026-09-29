import type { ApiError } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly data: ApiError,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string | null,
): Promise<T> {
  const request = async (token?: string | null) => {
    const headers = new Headers(options.headers);
    if (
      options.body &&
      !(options.body instanceof FormData) &&
      !headers.has("Content-Type")
    )
      headers.set("Content-Type", "application/json");
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(`${API_BASE}${path}`, { ...options, headers });
  };
  let response = await request(accessToken);
  if (response.status === 401 && accessToken && !path.includes("/auth/")) {
    const refresh = sessionStorage.getItem("deverp.refresh");
    if (refresh) {
      const refreshResponse = await fetch(`${API_BASE}/auth/token/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });
      if (refreshResponse.ok) {
        const tokens = (await refreshResponse.json()) as {
          access: string;
          refresh?: string;
        };
        sessionStorage.setItem("deverp.access", tokens.access);
        if (tokens.refresh)
          sessionStorage.setItem("deverp.refresh", tokens.refresh);
        response = await request(tokens.access);
      } else {
        sessionStorage.removeItem("deverp.access");
        sessionStorage.removeItem("deverp.refresh");
        sessionStorage.removeItem("deverp.user");
        window.dispatchEvent(new Event("deverp:session-expired"));
      }
    } else {
      sessionStorage.removeItem("deverp.access");
      sessionStorage.removeItem("deverp.refresh");
      sessionStorage.removeItem("deverp.user");
      window.dispatchEvent(new Event("deverp:session-expired"));
    }
  }
  if (response.status === 204) return undefined as T;
  const data = (await response.json().catch(() => ({}))) as ApiError;
  if (!response.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : Object.values(data)
            .flatMap((value) => (Array.isArray(value) ? value : []))
            .join(" ") || `Request failed (${response.status}).`;
    throw new ApiRequestError(detail, response.status, data);
  }
  return data as T;
}

function errorFromResponse(status: number, data: ApiError): ApiRequestError {
  const detail =
    typeof data.detail === "string"
      ? data.detail
      : Object.values(data)
          .flatMap((value) => (Array.isArray(value) ? value : []))
          .join(" ") || `Request failed (${status}).`;
  return new ApiRequestError(detail, status, data);
}

export async function apiDownload(
  path: string,
  filename: string,
  accessToken?: string | null,
): Promise<void> {
  let token = accessToken;
  let response = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (response.status === 401 && token) {
    const refresh = sessionStorage.getItem("deverp.refresh");
    if (!refresh) {
      window.dispatchEvent(new Event("deverp:session-expired"));
    } else {
      let refreshed: { access: string; refresh?: string };
      try {
        refreshed = await apiRequest<{ access: string; refresh?: string }>(
          "/auth/token/refresh/",
          { method: "POST", body: JSON.stringify({ refresh }) },
        );
      } catch (error) {
        sessionStorage.removeItem("deverp.access");
        sessionStorage.removeItem("deverp.refresh");
        sessionStorage.removeItem("deverp.user");
        window.dispatchEvent(new Event("deverp:session-expired"));
        throw error;
      }
      token = refreshed.access;
      sessionStorage.setItem("deverp.access", token);
      if (refreshed.refresh)
        sessionStorage.setItem("deverp.refresh", refreshed.refresh);
      response = await fetch(`${API_BASE}${path}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    }
  }
  if (!response.ok) {
    const data = (await response.json().catch(() => ({}))) as ApiError;
    throw errorFromResponse(response.status, data);
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
