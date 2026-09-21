import { PenLine, Timer } from "lucide-react";
import { memo } from "react";

import { CategoryTag } from "@/components/ui/CategoryTag";
import { UrgencyBadge } from "@/components/ui/UrgencyBadge";
import { useNow } from "@/hooks/useNow";
import { REVIEW_THRESHOLD } from "@/lib/constants";
import type { TicketSummary } from "@/lib/types";
import { cn, formatMinutes, slaMinutesRemaining, timeAgo } from "@/lib/utils";

function SlaChip({ ticket, now }: { ticket: TicketSummary; now: number }) {
  if (ticket.status === "Resolved") return null;

  const remaining = slaMinutesRemaining(ticket.created_at, ticket.sla_minutes, now);

  if (remaining < 0) {
    return (
      <span
        className="inline-flex items-center gap-1 font-mono text-[10.5px] text-critical"
        title="First-response SLA breached"
      >
        <Timer className="size-3" aria-hidden />
        {formatMinutes(-remaining)} over
      </span>
    );
  }

  // Only surface the countdown in the last quarter of the budget; showing it
  // on every card would bury the ones that actually need attention.
  if (remaining < ticket.sla_minutes * 0.25) {
    return (
      <span
        className="inline-flex items-center gap-1 font-mono text-[10.5px] text-medium"
        title="Approaching first-response SLA"
      >
        <Timer className="size-3" aria-hidden />
        {formatMinutes(remaining)} left
      </span>
    );
  }

  return null;
}

interface TicketCardProps {
  ticket: TicketSummary;
  fresh?: boolean;
  overlay?: boolean;
  dimmed?: boolean;
}

export const TicketCard = memo(function TicketCard({
  ticket,
  fresh = false,
  overlay = false,
  dimmed = false,
}: TicketCardProps) {
  const now = useNow();

  // Once an agent has corrected a field it is no longer the model's guess, so
  // the low-confidence marker no longer applies to it.
  const urgencyUncertain =
    ticket.urgency === ticket.ai_urgency &&
    ticket.ai_urgency_confidence < REVIEW_THRESHOLD.urgency;
  const categoryUncertain =
    ticket.category === ticket.ai_category &&
    ticket.ai_category_confidence < REVIEW_THRESHOLD.category;

  const severe = ticket.urgency === "Critical" || ticket.urgency === "High";

  return (
    <article
      className={cn(
        "group relative overflow-hidden rounded-xl border border-line bg-surface p-3.5 text-left shadow-panel",
        "transition-[border-color,box-shadow,opacity] duration-150 hover:border-line-strong",
        fresh && "animate-arrive",
        overlay && "rotate-[1.5deg] cursor-grabbing border-line-strong shadow-overlay",
        dimmed && "opacity-40",
      )}
    >
      {severe && (
        <span
          aria-hidden
          className={cn(
            "absolute inset-y-3 left-0 w-0.5 rounded-r-full",
            ticket.urgency === "Critical" ? "bg-critical" : "bg-high/70",
          )}
        />
      )}

      <div className="mb-1.5 flex items-center gap-1.5 font-mono text-[10.5px] text-fg-subtle">
        <span>{ticket.reference}</span>
        <span aria-hidden>·</span>
        <time dateTime={ticket.created_at}>{timeAgo(ticket.created_at, now)}</time>
        {fresh && (
          <span className="ml-auto rounded-full bg-accent-soft px-1.5 py-px font-sans text-[10px] font-semibold uppercase tracking-wide text-accent">
            New
          </span>
        )}
      </div>

      <h3 className="line-clamp-2 text-[13px] font-medium leading-snug text-fg">{ticket.subject}</h3>
      <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-fg-muted">{ticket.preview}</p>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <UrgencyBadge urgency={ticket.urgency} uncertain={urgencyUncertain} />
        <CategoryTag category={ticket.category} compact uncertain={categoryUncertain} />
        {ticket.was_overridden && (
          <span className="text-fg-subtle" title="An agent corrected the AI's prediction">
            <PenLine className="size-3" aria-label="Corrected by an agent" />
          </span>
        )}
        <span className="ml-auto">
          <SlaChip ticket={ticket} now={now} />
        </span>
      </div>
    </article>
  );
});
