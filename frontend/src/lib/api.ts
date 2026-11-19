import createClient from "openapi-fetch";
import type { paths } from "./api-types";
import { getCookie } from "./cookies";

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const CSRF_COOKIE = "wl_csrf";
const CSRF_HEADER = "X-CSRF-Token";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryAfter: number | null;

  constructor(message: string, code = "request_failed", status = 0, retryAfter: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL ?? "",
  credentials: "include",
});

let csrfRequest: Promise<void> | null = null;

export async function ensureCsrf(): Promise<void> {
  if (getCookie(CSRF_COOKIE)) return;
  if (!csrfRequest) {
    csrfRequest = api
      .GET("/api/auth/csrf")
      .then((result) => {
        if (!result.response.ok) {
          throw new ApiError("Could not start a session.", "csrf_failed", result.response.status);
        }
      })
      .finally(() => {
        csrfRequest = null;
      });
  }
  await csrfRequest;
}

api.use({
  async onRequest({ request }) {
    if (!UNSAFE_METHODS.has(request.method)) return;
    await ensureCsrf();
    const token = getCookie(CSRF_COOKIE);
    if (!token) return;
    const headers = new Headers(request.headers);
    headers.set(CSRF_HEADER, token);
    return new Request(request, { headers });
  },
});

type Result<T> = {
  data?: T;
  error?: unknown;
  response: Response;
};

export async function unwrap<T>(pending: Promise<Result<T>>): Promise<T> {
  const result = await pending;
  if (result.response.ok) {
    return result.data as T;
  }

  let code = "request_failed";
  let message = `Request failed with status ${result.response.status}.`;

  const payload = result.error as
    | { error?: { code?: string; message?: string } }
    | undefined;
  if (payload && typeof payload === "object" && payload.error) {
    if (payload.error.code) code = payload.error.code;
    if (payload.error.message) message = payload.error.message;
  }

  const retryAfterHeader = result.response.headers.get("Retry-After");
  const retryAfter = retryAfterHeader ? Number(retryAfterHeader) : null;

  throw new ApiError(
    message,
    code,
    result.response.status,
    retryAfter !== null && Number.isFinite(retryAfter) ? retryAfter : null,
  );
}
