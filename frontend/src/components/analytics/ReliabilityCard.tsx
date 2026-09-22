import { motion } from "framer-motion";
import { ArrowRight, PenLine } from "lucide-react";

import { useNow } from "@/hooks/useNow";
import type { OverrideStats } from "@/lib/types";
import { cn, formatPercent, timeAgo } from "@/lib/utils";

// Reads the two confidence averages together. A raw override count cannot tell
// "agents fixed the calls the model flagged as shaky" (the system working)
// apart from "agents fixed calls the model was sure about" (the model is wrong
// and doesn't know it).
function verdict(stats: OverrideStats): { tone: string; text: string } {
  if (stats.overridden_tickets === 0) {
    return { tone: "text-fg-muted", text: "No corrections logged yet — this fills in as agents work the queue." };
  }
  const gap = stats.avg_confidence_when_accepted - stats.avg_confidence_when_overridden;
  if (gap >= 0.08) {
    return {
      tone: "text-low",
      text: "Agents mostly correct calls the model was unsure about — confidence is doing its job.",
    };
  }
  if (gap <= 0) {
    return {
      tone: "text-critical",
      text: "Corrections are landing on confident predictions — the model may be wrong without knowing it.",
    };
  }
  return {
    tone: "text-medium",
    text: "Corrected and accepted calls look similar in confidence — worth watching as traffic grows.",
  };
}

function ConfidenceBar({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div>
      <div className="mb-1 flex justify-between gap-3 text-xs">
        <span className="text-fg-muted">{label}</span>
        <span className="font-mono tabular-nums">{formatPercent(value)}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-3">
        <motion.div
          className={cn("h-full rounded-full", tone)}
          initial={{ width: 0 }}
          animate={{ width: `${value * 100}%` }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>
    </div>
  );
}

export function ReliabilityCard({ stats }: { stats: OverrideStats }) {
  const now = useNow();
  const judgement = verdict(stats);

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="space-y-5">
        <div>
          <p className="font-mono text-4xl font-semibold tracking-tight tabular-nums">
            {formatPercent(stats.override_rate, 1)}
          </p>
          <p className="mt-1 text-xs text-fg-muted">
            of tickets corrected by an agent · {stats.overridden_tickets} of {stats.total_tickets}
          </p>
        </div>

        <div className="space-y-3">
          <ConfidenceBar label="Model confidence on accepted calls" value={stats.avg_confidence_when_accepted} tone="bg-low" />
          <ConfidenceBar label="Model confidence on corrected calls" value={stats.avg_confidence_when_overridden} tone="bg-medium" />
        </div>

        <p className={cn("text-xs leading-relaxed", judgement.tone)}>{judgement.text}</p>

        <div className="flex flex-wrap gap-2 text-[11px] text-fg-muted">
          <span className="rounded-md border border-line bg-surface-2 px-2 py-1">
            <span className="font-mono text-fg">{stats.urgency_overrides}</span> urgency
          </span>
          <span className="rounded-md border border-line bg-surface-2 px-2 py-1">
            <span className="font-mono text-fg">{stats.category_overrides}</span> category
          </span>
          <span className="rounded-md border border-line bg-surface-2 px-2 py-1">
            <span className="font-mono text-fg">{formatPercent(stats.low_confidence_share)}</span> under 50%
            confidence
          </span>
        </div>
      </div>

      <div className="min-w-0">
        <p className="mb-1.5 text-[11px] font-medium text-fg-subtle">Latest corrections</p>
        {stats.recent.length === 0 ? (
          <p className="text-xs text-fg-subtle">None yet.</p>
        ) : (
          <ul className="divide-y divide-line">
            {stats.recent.slice(0, 6).map((override) => (
              <li
                key={`${override.reference}-${override.field}-${override.created_at}`}
                className="flex items-center gap-3 py-2 text-xs"
              >
                <span className="grid size-6 shrink-0 place-items-center rounded-full bg-surface-3 text-fg-muted">
                  <PenLine className="size-3" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate">
                    <span className="font-mono text-fg-subtle">{override.reference}</span>{" "}
                    <span className="text-fg-muted">{override.field}</span>
                  </p>
                  <p className="flex items-center gap-1 truncate">
                    <span className="text-fg-subtle line-through">{override.from_value}</span>
                    <ArrowRight className="size-3 shrink-0 text-fg-subtle" />
                    <span className="font-medium">{override.to_value}</span>
                  </p>
                </div>
                <div className="shrink-0 text-right font-mono text-[10.5px] leading-relaxed text-fg-subtle">
                  <p>{formatPercent(override.model_confidence)} conf.</p>
                  <p>{timeAgo(override.created_at, now)}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
