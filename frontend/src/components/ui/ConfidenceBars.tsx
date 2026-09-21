import { motion } from "framer-motion";

import { CATEGORY_TONE, URGENCY_TONE } from "@/lib/constants";
import type { Category, LabelScore, Urgency } from "@/lib/types";
import { cn, formatPercent } from "@/lib/utils";

export const urgencyBarTone = (label: string) =>
  URGENCY_TONE[label as Urgency]?.dot ?? "bg-accent";

export const categoryBarTone = (label: string) =>
  CATEGORY_TONE[label as Category]?.dot ?? "bg-accent";

interface ConfidenceBarsProps {
  scores: LabelScore[];
  toneFor: (label: string) => string;
  highlight?: string;
  threshold?: number;
  className?: string;
}

export function ConfidenceBars({
  scores,
  toneFor,
  highlight,
  threshold,
  className,
}: ConfidenceBarsProps) {
  return (
    <ul className={cn("space-y-2", className)}>
      {scores.map((score, index) => {
        const active = score.label === highlight;

        return (
          <li
            key={score.label}
            className="grid grid-cols-[7.5rem_1fr_3rem] items-center gap-3 text-xs"
          >
            <span className={cn("truncate", active ? "font-medium text-fg" : "text-fg-muted")}>
              {score.label}
            </span>

            <span className="relative h-2 overflow-hidden rounded-full bg-surface-3">
              <motion.span
                className={cn(
                  "absolute inset-y-0 left-0 rounded-full",
                  toneFor(score.label),
                  !active && "opacity-40",
                )}
                initial={{ width: 0 }}
                animate={{ width: `${Math.max(score.confidence * 100, 1.5)}%` }}
                transition={{ duration: 0.6, delay: 0.04 * index, ease: [0.22, 1, 0.36, 1] }}
              />
              {threshold !== undefined && active && (
                <span
                  className="absolute inset-y-0 w-px bg-fg/50"
                  style={{ left: `${threshold * 100}%` }}
                  title={`Review threshold ${formatPercent(threshold)}`}
                />
              )}
            </span>

            <span
              className={cn(
                "text-right font-mono tabular-nums",
                active ? "text-fg" : "text-fg-subtle",
              )}
            >
              {formatPercent(score.confidence)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
