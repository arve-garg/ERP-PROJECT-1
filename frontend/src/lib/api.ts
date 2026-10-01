import type { ApiError } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const SESSION_KEYS = ["deverp.access", "deverp.refresh", "deverp.user"];

interface RefreshResponse {
  access: string;
  refresh?: string;
}

let refreshInFlight: Promise<RefreshResponse | null> | null = null;

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

function expireSession() {
  SESSION_KEYS.forEach((key) => sessionStorage.removeItem(key));
  window.dispatchEvent(new Event("deverp:session-expired"));
}

export async function refreshAccessToken(): Promise<RefreshResponse | null> {
  const refresh = sessionStorage.getItem("deverp.refresh");
  if (!refresh) {
    expireSession();
    return null;
  }
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_BASE}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    })
      .then(async (response) => {
        const tokens = (await response.json().catch(() => ({}))) as Partial<RefreshResponse>;
        if (!response.ok || typeof tokens.access !== "string" || !tokens.access) {
          expireSession();
          return null;
        }
        sessionStorage.setItem("deverp.access", tokens.access);
        if (typeof tokens.refresh === "string" && tokens.refresh) {
          sessionStorage.setItem("deverp.refresh", tokens.refresh);
        }
        return tokens as RefreshResponse;
      })
      .catch(() => {
        expireSession();
        return null;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
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
  if (response.status === 401 && accessToken && !path.startsWith("/auth/")) {
    const tokens = await refreshAccessToken();
    if (tokens) {
      response = await request(tokens.access);
      if (response.status === 401) expireSession();
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
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      token = refreshed.access;
      response = await fetch(`${API_BASE}${path}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.status === 401) expireSession();
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
