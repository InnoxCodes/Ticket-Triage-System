import type { Category, Status, Urgency } from "./types";

// Canonical ordering mirrors backend/app/ml/taxonomy.py, so filters, chart
// legends and the confusion matrix all list labels in the same order.
export const CATEGORIES: readonly Category[] = [
  "Billing",
  "Bug Report",
  "Login/Access",
  "Feature Request",
  "General Inquiry",
  "Technical Issue",
];

export const URGENCIES: readonly Urgency[] = ["Critical", "High", "Medium", "Low"];
export const STATUSES: readonly Status[] = ["Open", "In Progress", "Resolved"];

// Mirrors CONFIDENCE_REVIEW_THRESHOLD in the backend taxonomy.
export const REVIEW_THRESHOLD = { category: 0.55, urgency: 0.45 } as const;

export interface Tone {
  cssVar: string;
  dot: string;
  text: string;
  soft: string;
  border: string;
}

// Full class strings, never assembled at runtime, so Tailwind's scanner sees every one.
export const URGENCY_TONE: Record<Urgency, Tone> = {
  Critical: {
    cssVar: "--critical",
    dot: "bg-critical",
    text: "text-critical",
    soft: "bg-critical-soft",
    border: "border-critical/30",
  },
  High: {
    cssVar: "--high",
    dot: "bg-high",
    text: "text-high",
    soft: "bg-high-soft",
    border: "border-high/30",
  },
  Medium: {
    cssVar: "--medium",
    dot: "bg-medium",
    text: "text-medium",
    soft: "bg-medium-soft",
    border: "border-medium/30",
  },
  Low: {
    cssVar: "--low",
    dot: "bg-low",
    text: "text-low",
    soft: "bg-low-soft",
    border: "border-low/30",
  },
};

export const CATEGORY_TONE: Record<Category, Tone & { short: string }> = {
  Billing: {
    cssVar: "--cat-billing",
    dot: "bg-cat-billing",
    text: "text-cat-billing",
    soft: "bg-cat-billing/10",
    border: "border-cat-billing/25",
    short: "Billing",
  },
  "Bug Report": {
    cssVar: "--cat-bug",
    dot: "bg-cat-bug",
    text: "text-cat-bug",
    soft: "bg-cat-bug/10",
    border: "border-cat-bug/25",
    short: "Bug",
  },
  "Login/Access": {
    cssVar: "--cat-access",
    dot: "bg-cat-access",
    text: "text-cat-access",
    soft: "bg-cat-access/10",
    border: "border-cat-access/25",
    short: "Access",
  },
  "Feature Request": {
    cssVar: "--cat-feature",
    dot: "bg-cat-feature",
    text: "text-cat-feature",
    soft: "bg-cat-feature/10",
    border: "border-cat-feature/25",
    short: "Feature",
  },
  "General Inquiry": {
    cssVar: "--cat-inquiry",
    dot: "bg-cat-inquiry",
    text: "text-cat-inquiry",
    soft: "bg-cat-inquiry/10",
    border: "border-cat-inquiry/25",
    short: "Inquiry",
  },
  "Technical Issue": {
    cssVar: "--cat-technical",
    dot: "bg-cat-technical",
    text: "text-cat-technical",
    soft: "bg-cat-technical/10",
    border: "border-cat-technical/25",
    short: "Technical",
  },
};

export const STATUS_META: Record<Status, { dot: string; hint: string }> = {
  Open: { dot: "bg-accent", hint: "Waiting for an agent" },
  "In Progress": { dot: "bg-cat-technical", hint: "Being worked" },
  Resolved: { dot: "bg-low", hint: "Closed out" },
};

export const THEME_STORAGE_KEY = "triageai-theme";
