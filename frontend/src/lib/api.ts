import type {
  Agent,
  AnalyticsSummary,
  Category,
  Health,
  ModelPerformance,
  PredictionPreview,
  SimulatorState,
  Status,
  TicketCreate,
  TicketDetail,
  TicketPage,
  TicketUpdate,
  TokenResponse,
  Urgency,
} from "./types";

export const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");

export function websocketUrl(path: string): string {
  if (API_BASE) return `${API_BASE.replace(/^http/, "ws")}${path}`;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

export class ApiError extends Error {
  readonly status: number;
  readonly fieldErrors: Record<string, string>;

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

// Module-level so non-React code paths (the query client, the feed socket)
// share one source of truth for the current session.
let authToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

type QueryParams = Record<string, string | number | boolean | null | undefined>;

interface RequestOptions {
  body?: unknown;
  query?: QueryParams;
  auth?: boolean;
  signal?: AbortSignal;
}

function toQueryString(params?: QueryParams): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

function toApiError(status: number, payload: unknown): ApiError {
  const fallback = status >= 500 ? "Something went wrong on the server." : `Request failed (${status})`;
  if (!payload || typeof payload !== "object") return new ApiError(status, fallback);

  const { detail, errors } = payload as { detail?: unknown; errors?: unknown };
  const fieldErrors: Record<string, string> = {};

  if (Array.isArray(errors)) {
    for (const error of errors) {
      if (error && typeof error === "object" && "field" in error && "message" in error) {
        fieldErrors[String(error.field)] = String(error.message);
      }
    }
  }

  return new ApiError(status, typeof detail === "string" ? detail : fallback, fieldErrors);
}

async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const { body, query, auth = true, signal } = options;

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && authToken) headers.Authorization = `Bearer ${authToken}`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api${path}${toQueryString(query)}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "Can't reach the TriageAI API. Is the backend running?");
  }

  if (response.status === 204) return undefined as T;

  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    // Only a request that carried a token can mean "your session expired";
    // a 401 from the login form is just a wrong password.
    if (response.status === 401 && auth && authToken) unauthorizedHandler?.();
    throw toApiError(response.status, payload);
  }

  return payload as T;
}

export type TicketQuery = {
  page?: number;
  page_size?: number;
  category?: Category;
  urgency?: Urgency;
  status?: Status;
  needs_review?: boolean;
  overridden?: boolean;
  search?: string;
  sort?: "newest" | "oldest" | "severity";
};

export const api = {
  login: (email: string, password: string) =>
    request<TokenResponse>("POST", "/auth/login", { body: { email, password }, auth: false }),
  me: () => request<Agent>("GET", "/auth/me"),
  health: () => request<Health>("GET", "/health", { auth: false }),

  listTickets: (query: TicketQuery = {}) =>
    request<TicketPage>("GET", "/tickets", { query: { ...query } }),
  getTicket: (id: number, signal?: AbortSignal) =>
    request<TicketDetail>("GET", `/tickets/${id}`, { signal }),
  updateTicket: (id: number, patch: TicketUpdate) =>
    request<TicketDetail>("PATCH", `/tickets/${id}`, { body: patch }),
  deleteTicket: (id: number) => request<void>("DELETE", `/tickets/${id}`),

  createTicket: (payload: TicketCreate) =>
    request<TicketDetail>("POST", "/tickets", { body: payload, auth: false }),
  classify: (payload: TicketCreate, signal?: AbortSignal) =>
    request<PredictionPreview>("POST", "/tickets/classify", { body: payload, auth: false, signal }),

  analytics: (days = 14) =>
    request<AnalyticsSummary>("GET", "/analytics/summary", { query: { days } }),
  modelPerformance: () => request<ModelPerformance>("GET", "/analytics/model"),

  simulator: () => request<SimulatorState>("GET", "/simulator"),
  startSimulator: () => request<SimulatorState>("POST", "/simulator/start"),
  stopSimulator: () => request<SimulatorState>("POST", "/simulator/stop"),
};
