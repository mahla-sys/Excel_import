/**
 * Thin fetch wrapper with:
 * - same-origin credentials so HttpOnly auth cookies are attached
 * - double-submit CSRF: reads the readable csrf cookie and sends it as
 *   X-CSRFToken on state-changing requests
 * - automatic access-token refresh on 401 (queued concurrent requests
 *   share a single refresh call). Sensitive token values never enter
 *   localStorage/sessionStorage.
 */

const BASE_URL = "/api/v1";
const REFRESH_PATH = "/auth/refresh/";
const LOGIN_PATH = "/auth/login/";

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()!.split(";").shift()!;
  return null;
}

type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export interface RequestOptions {
  method?: Method;
  body?: unknown;
  signal?: AbortSignal;
  headers?: Record<string, string>;
  // If true, skip the JSON body parsing (used for file downloads).
  rawResponse?: boolean;
  // If true, do not attempt a refresh even on 401 (used by refresh itself).
  skipAuthRefresh?: boolean;
}

let refreshInFlight: Promise<boolean> | null = null;

async function performRefresh(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const csrf = getCookie("csrf_token");
        const resp = await fetch(`${BASE_URL}${REFRESH_PATH}`, {
          method: "POST",
          credentials: "same-origin",
          headers: csrf ? { "X-CSRFToken": csrf } : {},
        });
        return resp.ok;
      } catch {
        return false;
      } finally {
        // Clear the in-flight lock after a tick so any concurrent requests
        // that observed it have a chance to await.
        setTimeout(() => {
          refreshInFlight = null;
        }, 0);
      }
    })();
  }
  return refreshInFlight;
}

function buildHeaders(method: Method, body: unknown, extra: Record<string, string>) {
  const csrfMethods: Method[] = ["POST", "PATCH", "PUT", "DELETE"];
  const csrfToken = getCookie("csrf_token");
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...extra,
  };
  if (body !== undefined && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (csrfMethods.includes(method) && csrfToken) {
    headers["X-CSRFToken"] = csrfToken;
  }
  return headers;
}

async function rawFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<{ response: Response; parsed: T | null }> {
  const {
    method = "GET",
    body,
    signal,
    headers = {},
  } = options;
  const url = path.startsWith("http") ? path : `${BASE_URL}${path}`;
  const finalHeaders = buildHeaders(method, body, headers);

  const response = await fetch(url, {
    method,
    credentials: "same-origin",
    headers: finalHeaders,
    body:
      body === undefined
        ? undefined
        : body instanceof FormData
          ? body
          : JSON.stringify(body),
    signal,
  });

  if (options.rawResponse) {
    return { response, parsed: null };
  }

  if (response.status === 204) {
    return { response, parsed: null };
  }

  const text = await response.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }
  return { response, parsed: parsed as T | null };
}

function extractError(response: Response, parsed: unknown): ApiError {
  const detail =
    parsed && typeof parsed === "object" && "detail" in parsed
      ? String((parsed as Record<string, unknown>).detail)
      : `درخواست با خطای ${response.status} مواجه شد.`;
  return new ApiError(response.status, detail, parsed);
}

export async function apiRequest<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { skipAuthRefresh = false } = options;
  let result = await rawFetch<T>(path, options);

  if (result.response.status === 401 && !skipAuthRefresh && !path.startsWith(LOGIN_PATH) && !path.startsWith(REFRESH_PATH)) {
    const refreshed = await performRefresh();
    if (refreshed) {
      result = await rawFetch<T>(path, options);
    }
    // If refresh fails, do NOT force-navigate here: this code runs for
    // every 401 including the initial "am I logged in?" check on first
    // load, and a hard window.location.assign("/login") on that request
    // reloads the page, which re-mounts the app, which re-fires the same
    // check -> infinite reload loop. Just let the 401 propagate; callers
    // (e.g. AuthContext's "me" query) already handle it, and the router's
    // RequireAuth/RedirectIfAuthed guards redirect without a full reload.
  }

  if (!result.response.ok) {
    throw extractError(result.response, result.parsed);
  }

  if (options.rawResponse) {
    return result.response as unknown as T;
  }
  return result.parsed as T;
}

/** Convenience helper for streaming file downloads. */
export function apiDownload(path: string): Promise<Response> {
  return apiRequest<Response>(path, { rawResponse: true });
}
