import { useDraggable, useDroppable } from "@dnd-kit/core";
import { AnimatePresence, motion } from "framer-motion";
import { CircleCheckBig, Hourglass, Inbox } from "lucide-react";
import type { KeyboardEvent } from "react";

import { TicketCard } from "@/components/tickets/TicketCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { STATUS_META } from "@/lib/constants";
import type { Status, TicketSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const EMPTY_COPY: Record<Status, { icon: typeof Inbox; title: string; description: string }> = {
  Open: {
    icon: Inbox,
    title: "Queue is clear",
    description: "New tickets slide in here the moment a customer submits one.",
  },
  "In Progress": {
    icon: Hourglass,
    title: "Nothing in flight",
    description: "Drag a ticket here when you start working on it.",
  },
  Resolved: {
    icon: CircleCheckBig,
    title: "Nothing resolved yet",
    description: "Tickets you close out land here.",
  },
};

export interface DragData {
  ticket: TicketSummary;
}

interface DraggableTicketProps {
  ticket: TicketSummary;
  fresh: boolean;
  onOpen: (ticketId: number) => void;
}

function DraggableTicket({ ticket, fresh, onOpen }: DraggableTicketProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: ticket.id,
    data: { ticket } satisfies DragData,
  });

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    // Space picks the card up (dnd-kit); Enter opens it.
    listeners?.onKeyDown?.(event);
    if (event.key === "Enter" && !event.defaultPrevented) onOpen(ticket.id);
  };

  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      onKeyDown={handleKeyDown}
      onClick={() => onOpen(ticket.id)}
      aria-label={`${ticket.reference}: ${ticket.subject}. ${ticket.urgency}, ${ticket.category}. Enter to open, Space to move.`}
      className="rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-(--ring)"
    >
      <TicketCard ticket={ticket} fresh={fresh} dimmed={isDragging} />
    </div>
  );
}

interface KanbanColumnProps {
  status: Status;
  tickets: TicketSummary[];
  limit: number;
  isFresh: (ticketId: number) => boolean;
  onOpen: (ticketId: number) => void;
}

export function KanbanColumn({ status, tickets, limit, isFresh, onOpen }: KanbanColumnProps) {
  const { setNodeRef, isOver, active } = useDroppable({ id: status });

  const sourceStatus = (active?.data.current as DragData | undefined)?.ticket.status;
  const canDrop = Boolean(active) && sourceStatus !== status;

  const visible = tickets.slice(0, limit);
  const hidden = tickets.length - visible.length;
  const critical = tickets.filter((ticket) => ticket.urgency === "Critical").length;
  const empty = EMPTY_COPY[status];

  return (
    <section
      ref={setNodeRef}
      aria-label={`${status} column`}
      className={cn(
        "flex min-h-[18rem] snap-start flex-col rounded-2xl border bg-surface-2/40 transition-colors duration-150 md:max-h-[calc(100dvh-12rem)]",
        isOver && canDrop
          ? "border-accent/60 bg-accent-soft"
          : canDrop
            ? "border-dashed border-line-strong"
            : "border-line",
      )}
    >
      <header className="flex items-center gap-2 px-3.5 pb-2 pt-3">
        <span className={cn("size-2 rounded-full", STATUS_META[status].dot)} aria-hidden />
        <h2 className="text-[13px] font-semibold text-fg">{status}</h2>
        <span className="rounded-md bg-surface-3 px-1.5 font-mono text-[11px] tabular-nums text-fg-muted">
          {tickets.length}
        </span>
        {status !== "Resolved" && critical > 0 && (
          <span className="ml-auto rounded-full bg-critical-soft px-2 py-0.5 text-[10.5px] font-medium text-critical">
            {critical} critical
          </span>
        )}
      </header>

      <div className="flex-1 space-y-2 overflow-y-auto px-2.5 pb-3 pt-1">
        {tickets.length === 0 ? (
          <EmptyState compact icon={empty.icon} title={empty.title} description={empty.description} />
        ) : (
          <AnimatePresence initial={false}>
            {visible.map((ticket) => (
              <motion.div
                key={ticket.id}
                layout="position"
                initial={{ opacity: 0, y: -14, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.97, transition: { duration: 0.15 } }}
                transition={{ type: "spring", stiffness: 420, damping: 34 }}
              >
                <DraggableTicket ticket={ticket} fresh={isFresh(ticket.id)} onOpen={onOpen} />
              </motion.div>
            ))}
          </AnimatePresence>
        )}

        {hidden > 0 && (
          <p className="px-2 pt-1 text-center text-xs text-fg-subtle">
            +{hidden} more — narrow the view with filters
          </p>
        )}
      </div>
    </section>
  );
}
