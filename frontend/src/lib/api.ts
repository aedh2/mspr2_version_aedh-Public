import { apiUrl } from "@/src/lib/config";
import type { ApiErrorPayload, PaginationMeta } from "@/src/types/domain";

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  auth?: boolean;
  retry?: boolean;
  query?: Record<string, string | number | boolean | null | undefined>;
};

type AuthHandlers = {
  getToken: () => string | null;
  setToken: (token: string | null) => void;
  onUnauthorized: () => void;
};

function asNumber(value: unknown, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizePaginationMeta(meta: unknown): PaginationMeta {
  if (!meta || typeof meta !== "object") {
    return { page: 1, pageSize: 10, total: 0, totalPages: 1 };
  }
  const source = meta as Record<string, unknown>;
  const page = asNumber(source.page, 1);
  const pageSize = asNumber(source.pageSize ?? source.page_size, 10);
  const total = asNumber(source.total, 0);
  const totalPages = asNumber(source.totalPages ?? source.total_pages ?? source.pages, Math.max(1, Math.ceil(total / pageSize)));

  return {
    ...source,
    page,
    pageSize,
    total,
    totalPages,
    page_size: asNumber(source.page_size ?? pageSize, pageSize),
    pages: asNumber(source.pages ?? totalPages, totalPages),
    total_pages: asNumber(source.total_pages ?? totalPages, totalPages)
  };
}

export class ApiClientError extends Error {
  status: number;
  code?: string;
  details?: unknown;

  constructor(status: number, error: ApiErrorPayload) {
    super(error.message || "Une erreur est survenue.");
    this.status = status;
    this.code = error.code;
    this.details = error.details;
  }
}

let authHandlers: AuthHandlers = {
  getToken: () => null,
  setToken: () => undefined,
  onUnauthorized: () => undefined
};
let refreshPromise: Promise<string | null> | null = null;

export function getAuthToken() {
  return authHandlers.getToken();
}

export function configureApiAuth(handlers: AuthHandlers) {
  authHandlers = handlers;
}

function urlFor(path: string, query?: RequestOptions["query"]) {
  const base = apiUrl.replace(/\/+$/, "");
  let normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (base.endsWith("/api") && normalizedPath.startsWith("/api/")) {
    normalizedPath = normalizedPath.slice(4);
  }
  const url = new URL(`${base}${normalizedPath}`);
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  return url.toString();
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = payload?.error || payload?.detail || payload || {};
    const message =
      error.message ||
      error.detail ||
      (Array.isArray(error) && error[0]?.msg ? error[0].msg : undefined) ||
      fallbackHttpMessage(response.status) ||
      response.statusText;
    throw new ApiClientError(response.status, {
      code: error.code || "http_error",
      message,
      details: error.details || error
    });
  }

  if (payload && typeof payload === "object" && "data" in payload) {
    return payload.data as T;
  }
  return payload as T;
}

function fallbackHttpMessage(status: number) {
  if (status === 401) return "Session expiree ou utilisateur non connecte.";
  if (status === 422) return "Donnees envoyees invalides pour cette action.";
  if (status >= 500) return "Erreur backend pendant le traitement de la requete.";
  return undefined;
}

function networkError(path: string, error: unknown) {
  if (process.env.NODE_ENV !== "production") {
    console.error("API request failed before response", { path, error });
  }
  return new ApiClientError(0, {
    code: "network_error",
    message: "Backend indisponible ou requete bloquee par le navigateur. Verifiez que l'API est demarree et que NEXT_PUBLIC_API_URL pointe vers le backend.",
    details: error instanceof Error ? error.message : error
  });
}

async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = rawRequest<{ access_token: string }>("/api/auth/refresh", {
      method: "POST",
      auth: false,
      retry: false
    })
      .then((data) => {
        authHandlers.setToken(data.access_token);
        return data.access_token;
      })
      .catch(() => {
        authHandlers.setToken(null);
        authHandlers.onUnauthorized();
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

async function rawRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");

  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }

  const token = authHandlers.getToken();
  if (options.auth !== false && token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(urlFor(path, options.query), {
      ...options,
      body,
      headers,
      credentials: "include"
    });
  } catch (error) {
    throw networkError(path, error);
  }

  if (response.status === 401 && options.auth !== false && options.retry !== false) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return rawRequest<T>(path, { ...options, retry: false });
    }
    throw new ApiClientError(401, { code: "unauthorized", message: "Session expiree." });
  }

  return parseResponse<T>(response);
}

export function apiRequest<T>(path: string, options: RequestOptions = {}) {
  return rawRequest<T>(path, options);
}

export async function apiFormData<T>(path: string, formData: FormData, options: Omit<RequestOptions, "body"> = {}) {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");

  const token = authHandlers.getToken();
  if (options.auth !== false && token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(urlFor(path, options.query), {
      ...options,
      body: formData,
      headers,
      credentials: "include"
    });
  } catch (error) {
    throw networkError(path, error);
  }

  if (response.status === 401 && options.auth !== false && options.retry !== false) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiFormData<T>(path, formData, { ...options, retry: false });
    }
    throw new ApiClientError(401, { code: "unauthorized", message: "Session expiree." });
  }

  return parseResponse<T>(response);
}

export async function apiList<T>(path: string, options: RequestOptions = {}) {
  const { body: _body, query: _query, auth: _auth, retry: _retry, ...fetchOptions } = options;
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  const token = authHandlers.getToken();
  if (options.auth !== false && token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  let response: Response;
  try {
    response = await fetch(urlFor(path, options.query), { ...fetchOptions, headers, credentials: "include" });
  } catch (error) {
    throw networkError(path, error);
  }
  if (response.status === 401 && options.auth !== false && options.retry !== false) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiList<T>(path, { ...options, retry: false });
    }
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = payload?.error || payload?.detail || payload || {};
    const message =
      error.message ||
      error.detail ||
      (Array.isArray(error) && error[0]?.msg ? error[0].msg : undefined) ||
      fallbackHttpMessage(response.status) ||
      response.statusText;
    throw new ApiClientError(response.status, {
      code: error.code || "http_error",
      message,
      details: error.details || error
    });
  }
  return { data: (payload.data || []) as T[], meta: normalizePaginationMeta(payload.meta) };
}
