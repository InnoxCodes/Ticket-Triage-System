import { URGENCY_TONE } from "@/lib/constants";
import type { Urgency } from "@/lib/types";
import { cn } from "@/lib/utils";

export function UrgencyDot({ urgency, pulse }: { urgency: Urgency; pulse?: boolean }) {
  const tone = URGENCY_TONE[urgency];
  const animated = pulse ?? urgency === "Critical";

  return (
    <span className="relative inline-flex size-2 shrink-0" aria-hidden>
      {animated && (
        <span className={cn("absolute inset-0 animate-pulse-ring rounded-full", tone.dot)} />
      )}
      <span className={cn("relative inline-flex size-2 rounded-full", tone.dot)} />
    </span>
  );
}

interface UrgencyBadgeProps {
  urgency: Urgency;
  size?: "sm" | "md";
  // A dashed outline marks a low-confidence prediction: visible on a scan of
  // the board, but quiet enough not to read as an alarm on half the cards.
  uncertain?: boolean;
  className?: string;
}

export function UrgencyBadge({ urgency, size = "sm", uncertain = false, className }: UrgencyBadgeProps) {
  const tone = URGENCY_TONE[urgency];

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border font-medium",
        size === "sm" ? "h-5 px-2 text-[11px]" : "h-6 px-2.5 text-xs",
        tone.soft,
        tone.text,
        uncertain ? "border-dashed border-current/45" : tone.border,
        className,
      )}
      title={uncertain ? `${urgency} (low model confidence)` : urgency}
    >
      <UrgencyDot urgency={urgency} />
      {urgency}
    </span>
  );
}
