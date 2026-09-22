import { AnimatePresence, motion } from "framer-motion";
import { useState, type ReactNode } from "react";

import { ConfidenceCurve } from "@/components/analytics/ConfidenceCurve";
import { ConfusionMatrix } from "@/components/analytics/ConfusionMatrix";
import { Segmented } from "@/components/tickets/Segmented";
import { CATEGORY_TONE, REVIEW_THRESHOLD } from "@/lib/constants";
import type { Category, ModelMetrics, ModelPerformance as ModelPerformanceData } from "@/lib/types";
import { cn, formatPercent } from "@/lib/utils";

type Target = "Category" | "Urgency";
const TARGETS: readonly Target[] = ["Category", "Urgency"];

const NOTES: Record<Target, string> = {
  Category:
    "Most errors sit between Bug Report and Technical Issue — the same line human triagers blur.",
  Urgency:
    "Accuracy hinges on whether the customer states their impact. When they don't, severity is genuinely ambiguous — which is why the ticket form asks for it.",
};

function SubHeading({ children }: { children: ReactNode }) {
  return (
    <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-subtle">{children}</p>
  );
}

function Headline({ label, value, hint, emphasis }: { label: string; value: string; hint?: string; emphasis?: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-line bg-surface-2/50 px-4 py-3">
      <p className="truncate text-[11px] text-fg-subtle">{label}</p>
      <p className={cn("mt-1 font-mono text-xl font-semibold tracking-tight tabular-nums", emphasis)}>{value}</p>
      {hint && <p className="mt-0.5 truncate text-[11px] text-fg-muted">{hint}</p>}
    </div>
  );
}

function Slices({ metrics }: { metrics: ModelMetrics }) {
  return (
    <ul className="space-y-2.5">
      {metrics.slices.map((slice) => (
        <li key={slice.name}>
          <div className="mb-1 flex justify-between gap-3 text-xs">
            <span className="truncate text-fg-muted">
              {slice.name} <span className="font-mono text-fg-subtle">n={slice.n}</span>
            </span>
            <span className="font-mono tabular-nums">{formatPercent(slice.accuracy)}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
            <motion.div
              className="h-full rounded-full bg-accent"
              initial={{ width: 0 }}
              animate={{ width: `${slice.accuracy * 100}%` }}
              transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

function PerClassTable({ metrics }: { metrics: ModelMetrics }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[26rem] text-xs">
        <thead>
          <tr className="text-left text-[10.5px] uppercase tracking-[0.06em] text-fg-subtle">
            <th className="pb-2 font-medium">Class</th>
            <th className="pb-2 text-right font-medium">Precision</th>
            <th className="pb-2 text-right font-medium">Recall</th>
            <th className="pb-2 pl-5 font-medium">F1</th>
            <th className="pb-2 text-right font-medium">Support</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {metrics.per_class.map((row) => (
            <tr key={row.label}>
              <td className="py-2 pr-3">{row.label}</td>
              <td className="py-2 text-right font-mono tabular-nums text-fg-muted">{row.precision.toFixed(2)}</td>
              <td className="py-2 text-right font-mono tabular-nums text-fg-muted">{row.recall.toFixed(2)}</td>
              <td className="py-2 pl-5">
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-3">
                    <div className="h-full rounded-full bg-accent" style={{ width: `${row.f1 * 100}%` }} />
                  </div>
                  <span className="font-mono tabular-nums">{row.f1.toFixed(2)}</span>
                </div>
              </td>
              <td className="py-2 text-right font-mono tabular-nums text-fg-subtle">{row.support}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Candidates({ metrics }: { metrics: ModelMetrics }) {
  return (
    <ul className="space-y-2">
      {metrics.model_selection.candidates.map((candidate) => {
        const shipped = candidate.model === "Logistic Regression";
        return (
          <li key={candidate.model} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 text-xs">
            <span className={cn("truncate", shipped ? "font-medium text-fg" : "text-fg-muted")}>
              {candidate.model}
              {shipped && (
                <span className="ml-1.5 rounded bg-accent-soft px-1.5 py-px text-[10px] font-medium text-accent">
                  shipped
                </span>
              )}
            </span>
            <span className="font-mono tabular-nums text-fg-muted">F1 {candidate.cv_macro_f1.toFixed(3)}</span>
            <div className="col-span-2 h-1.5 overflow-hidden rounded-full bg-surface-3">
              <div
                className={cn("h-full rounded-full", shipped ? "bg-accent" : "bg-fg-subtle/50")}
                style={{ width: `${candidate.cv_macro_f1 * 100}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function ModelPerformance({ data }: { data: ModelPerformanceData }) {
  const [target, setTarget] = useState<Target>("Category");

  const metrics = target === "Category" ? data.category : data.urgency;
  const threshold = target === "Category" ? REVIEW_THRESHOLD.category : REVIEW_THRESHOLD.urgency;
  const liftPoints = Math.round((metrics.accuracy - metrics.baseline_accuracy) * 100);
  const shortLabel = (label: string) =>
    target === "Category" ? (CATEGORY_TONE[label as Category]?.short ?? label) : label;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented label="Model" options={TARGETS} value={target} onChange={setTarget} className="w-56 grid-cols-2" />
        <p className="font-mono text-[11px] text-fg-subtle">
          trained{" "}
          {new Date(data.generated_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}{" "}
          · {data.dataset.total.toLocaleString()} tickets ({data.dataset.train}/{data.dataset.test} split) ·
          scikit-learn {data.environment.scikit_learn}
        </p>
      </div>

      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={target}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.2 }}
          className="space-y-6"
        >
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Headline
              label="Held-out accuracy"
              value={formatPercent(metrics.accuracy, 1)}
              hint={`+${liftPoints} pts over the ${formatPercent(metrics.baseline_accuracy)} baseline`}
            />
            <Headline label="Macro F1" value={metrics.macro_f1.toFixed(3)} hint="every class weighted equally" />
            {metrics.adjacent_accuracy !== undefined ? (
              <Headline
                label="Within one level"
                value={formatPercent(metrics.adjacent_accuracy, 1)}
                hint="off by at most one severity step"
                emphasis="text-low"
              />
            ) : (
              <Headline label="Weighted F1" value={metrics.weighted_f1.toFixed(3)} hint="weighted by class size" />
            )}
            <Headline label="Review threshold" value={formatPercent(threshold)} hint="below this, a human checks it" />
          </div>

          <p className="rounded-lg border border-line bg-surface-2/50 px-3.5 py-2.5 text-xs leading-relaxed text-fg-muted">
            {NOTES[target]}
          </p>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="min-w-0">
              <SubHeading>Confusion matrix</SubHeading>
              <ConfusionMatrix labels={metrics.labels} matrix={metrics.confusion_matrix} shortLabel={shortLabel} />
            </div>
            <div className="min-w-0">
              <SubHeading>Confidence threshold trade-off</SubHeading>
              <ConfidenceCurve curve={metrics.confidence_curve} threshold={threshold} />
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <div className="min-w-0">
              <SubHeading>Per-class metrics</SubHeading>
              <PerClassTable metrics={metrics} />
            </div>
            <div className="min-w-0 space-y-6">
              {metrics.slices.length > 0 && (
                <div>
                  <SubHeading>Where it's right and wrong</SubHeading>
                  <Slices metrics={metrics} />
                </div>
              )}
              {metrics.model_selection.candidates.length > 0 && (
                <div>
                  <SubHeading>Candidates compared (5-fold CV)</SubHeading>
                  <Candidates metrics={metrics} />
                  <p className="mt-2.5 text-[11px] leading-relaxed text-fg-subtle">
                    Linear SVM scores about the same but gives no calibrated probabilities, which the
                    confidence bars depend on.
                  </p>
                </div>
              )}
            </div>
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
