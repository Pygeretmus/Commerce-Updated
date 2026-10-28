// A small fetch wrapper: JSON in and out, JWT in the Authorization header, one automatic token refresh,
// and the API's error format turned into an ApiError with helpers for forms.

export const API_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";

const STORAGE_KEY = "commerce.tokens";

interface Tokens {
  access: string;
  refresh: string;
}

export interface ApiFieldError {
  param: string | null;
  message: string;
  code: string;
}

export class ApiError extends Error {
  status: number;
  errors: ApiFieldError[];
  retryAfter: number | null;

  constructor(
    status: number,
    errors: ApiFieldError[],
    retryAfter: number | null = null,
  ) {
    super(errors[0]?.message ?? `Request failed (${status})`);
    this.status = status;
    this.errors = errors;
    this.retryAfter = retryAfter;
  }

  /** The error of one form field, if the server reported one. */
  field(name: string): string | undefined {
    return this.errors.find((e) => e.param === name)?.message;
  }

  /** Errors that do not belong to any field (shown above the form). */
  get general(): string[] {
    return this.errors
      .filter((e) => !e.param || e.param === "non_field_errors")
      .map((e) => e.message);
  }

  has(code: string): boolean {
    return this.errors.some((e) => e.code === code);
  }
}

// --- token storage -----------------------------------------------------------------------------------

function readTokens(): Tokens | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Tokens) : null;
  } catch {
    return null;
  }
}

export function saveTokens(tokens: Tokens | null): void {
  try {
    if (tokens) localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* private mode: the session lasts until the page is closed */
  }
  memoryTokens = tokens;
}

let memoryTokens: Tokens | null = readTokens();

export function hasTokens(): boolean {
  return memoryTokens !== null;
}

type LogoutListener = () => void;
const logoutListeners = new Set<LogoutListener>();
export function onForcedLogout(listener: LogoutListener): () => void {
  logoutListeners.add(listener);
  return () => logoutListeners.delete(listener);
}

// --- requests ----------------------------------------------------------------------------------------

type Query = Record<string, string | number | boolean | null | undefined>;

interface Options {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Query;
  signal?: AbortSignal;
  /** Do not send the token (login, register) and do not try to refresh on 401. */
  anonymous?: boolean;
}

function buildUrl(path: string, query?: Query): string {
  const base = API_URL.startsWith("http")
    ? API_URL
    : `${window.location.origin}${API_URL}`;
  const url = new URL(`${base.replace(/\/$/, "")}${path}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (
      value !== undefined &&
      value !== null &&
      value !== "" &&
      value !== false
    )
      url.searchParams.set(key, String(value));
  }
  return url.toString();
}

async function parseError(response: Response): Promise<ApiError> {
  const retry = response.headers.get("Retry-After");
  let errors: ApiFieldError[] = [];
  try {
    const data = await response.json();
    if (Array.isArray(data?.errors)) errors = data.errors;
    else if (typeof data?.detail === "string")
      errors = [{ param: null, message: data.detail, code: "error" }];
  } catch {
    /* not JSON */
  }
  if (response.status === 429) {
    const wait = retry
      ? ` Try again in ${retry} seconds.`
      : " Try again in a moment.";
    errors = [
      { param: null, message: `Too many requests.${wait}`, code: "throttled" },
    ];
  }
  if (errors.length === 0)
    errors = [
      {
        param: null,
        message: "Something went wrong. Please try again.",
        code: "error",
      },
    ];
  return new ApiError(response.status, errors, retry ? Number(retry) : null);
}

let refreshing: Promise<boolean> | null = null;

/** Exchanges the refresh token for a new access token. Parallel callers share one request. */
function refreshAccess(): Promise<boolean> {
  refreshing ??= (async () => {
    const tokens = memoryTokens;
    if (!tokens) return false;
    try {
      const response = await fetch(buildUrl("/token/refresh/"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: tokens.refresh }),
      });
      if (!response.ok) return false;
      const data = (await response.json()) as {
        access: string;
        refresh?: string;
      };
      saveTokens({
        access: data.access,
        refresh: data.refresh ?? tokens.refresh,
      });
      return true;
    } catch {
      return false;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const { method = "GET", body, query, signal, anonymous = false } = options;

  const send = () => {
    const headers: Record<string, string> = {};
    if (!anonymous && memoryTokens)
      headers.Authorization = `Bearer ${memoryTokens.access}`;
    let payload: BodyInit | undefined;
    if (body instanceof FormData) payload = body;
    else if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    return fetch(buildUrl(path, query), {
      method,
      headers,
      body: payload,
      signal,
    });
  };

  let response = await send();
  if (response.status === 401 && !anonymous && memoryTokens) {
    if (await refreshAccess()) response = await send();
    else {
      saveTokens(null);
      logoutListeners.forEach((listener) => listener());
    }
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// --- WebSocket address ---------------------------------------------------------------------------------

/** `/api` on the same site becomes `ws(s)://site/ws`; an absolute API address keeps its host. */
export function wsUrl(path: string): string {
  const base = API_URL.startsWith("http")
    ? new URL(API_URL)
    : new URL(window.location.origin);
  const scheme = base.protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${base.host}${path}`;
}
