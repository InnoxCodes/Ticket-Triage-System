// API contract. Mirrors the Pydantic schemas in backend/app/schemas.

export type Category =
  | "Billing"
  | "Bug Report"
  | "Login/Access"
  | "Feature Request"
  | "General Inquiry"
  | "Technical Issue";

export type Urgency = "Critical" | "High" | "Medium" | "Low";
export type Status = "Open" | "In Progress" | "Resolved";
export type PredictionField = "category" | "urgency";

export interface LabelScore {
  label: string;
  confidence: number;
}

export interface TokenContribution {
  term: string;
  weight: number;
}

// ---- auth -----------------------------------------------------------------

export interface Agent {
  id: number;
  email: string;
  name: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  agent: Agent;
}

// ---- tickets --------------------------------------------------------------

export interface TicketSummary {
  id: number;
  reference: string;
  subject: string;
  preview: string;
  category: Category;
  urgency: Urgency;
  status: Status;
  ai_category: Category;
  ai_urgency: Urgency;
  ai_category_confidence: number;
  ai_urgency_confidence: number;
  ai_needs_review: boolean;
  was_overridden: boolean;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  sla_minutes: number;
  sla_breached: boolean;
}

export interface OverrideRecord {
  id: number;
  field: PredictionField;
  from_value: string;
  to_value: string;
  model_confidence: number;
  created_at: string;
  agent_name: string | null;
}

export interface TicketDetail extends TicketSummary {
  body: string;
  requester_email: string | null;
  ai_category_scores: LabelScore[];
  ai_urgency_scores: LabelScore[];
  ai_category_rationale: TokenContribution[];
  ai_urgency_rationale: TokenContribution[];
  model_version: string;
  inference_ms: number;
  overrides: OverrideRecord[];
}

export interface TicketPage {
  items: TicketSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface TicketCreate {
  subject: string;
  body: string;
  requester_email?: string | null;
}

export interface TicketUpdate {
  status?: Status;
  category?: Category;
  urgency?: Urgency;
}

export interface PredictionPreview {
  category: Category;
  category_confidence: number;
  category_scores: LabelScore[];
  category_rationale: TokenContribution[];
  category_needs_review: boolean;
  urgency: Urgency;
  urgency_confidence: number;
  urgency_scores: LabelScore[];
  urgency_rationale: TokenContribution[];
  urgency_needs_review: boolean;
  model_version: string;
  inference_ms: number;
}

// ---- analytics ------------------------------------------------------------

export interface CountBucket {
  label: string;
  count: number;
}

export interface TimeBucket {
  date: string;
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface RecentOverride {
  reference: string;
  field: PredictionField;
  from_value: string;
  to_value: string;
  model_confidence: number;
  created_at: string;
}

export interface OverrideStats {
  total_tickets: number;
  overridden_tickets: number;
  override_rate: number;
  category_overrides: number;
  urgency_overrides: number;
  low_confidence_share: number;
  avg_confidence_when_overridden: number;
  avg_confidence_when_accepted: number;
  by_field: CountBucket[];
  recent: RecentOverride[];
}

export interface AnalyticsSummary {
  total_tickets: number;
  open_tickets: number;
  in_progress_tickets: number;
  resolved_tickets: number;
  needs_review_tickets: number;
  critical_open: number;
  sla_breached: number;
  avg_resolution_minutes: number | null;
  median_resolution_minutes: number | null;
  avg_inference_ms: number;
  volume_over_time: TimeBucket[];
  by_category: CountBucket[];
  by_urgency: CountBucket[];
  by_status: CountBucket[];
  overrides: OverrideStats;
}

// ---- model performance ----------------------------------------------------

export interface PerClassMetric {
  label: string;
  precision: number;
  recall: number;
  f1: number;
  support: number;
}

export interface SliceMetric {
  name: string;
  n: number;
  accuracy: number;
}

export interface ConfidencePoint {
  threshold: number;
  coverage: number;
  n_auto_routed: number;
  accuracy: number;
  escalated_accuracy: number | null;
}

export interface CandidateModel {
  model: string;
  cv_accuracy: number;
  cv_accuracy_std: number;
  cv_macro_f1: number;
  fit_seconds: number;
}

export interface ModelMetrics {
  labels: string[];
  accuracy: number;
  macro_f1: number;
  weighted_f1: number;
  baseline_accuracy: number;
  adjacent_accuracy?: number;
  per_class: PerClassMetric[];
  confusion_matrix: number[][];
  top_features: Record<string, [string, number][]>;
  slices: SliceMetric[];
  confidence_curve: ConfidencePoint[];
  model_selection: {
    candidates: CandidateModel[];
    best_params: Record<string, string> | null;
    cv_best_score: number | null;
  };
}

export interface ModelPerformance {
  generated_at: string;
  dataset: { total: number; train: number; test: number; source: string };
  environment: { python: string; scikit_learn: string };
  category: ModelMetrics;
  urgency: ModelMetrics;
}

// ---- system ---------------------------------------------------------------

export interface Health {
  status: string;
  app: string;
  environment: string;
  model_loaded: boolean;
  model_version: string;
  ticket_count: number;
  websocket_clients: number;
  simulator_running: boolean;
}

export interface SimulatorState {
  running: boolean;
  interval_seconds: number;
}

// ---- realtime feed --------------------------------------------------------

export type FeedEvent =
  | {
      type: "ticket.created" | "ticket.updated" | "ticket.overridden";
      timestamp: string;
      data: TicketSummary;
    }
  | { type: "stats.invalidated"; timestamp: string; data: { deleted_id?: number } }
  | { type: "ready"; data: { agent: string } }
  | { type: "ping"; data: Record<string, never> };
