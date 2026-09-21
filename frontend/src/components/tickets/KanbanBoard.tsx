import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  MouseSensor,
  pointerWithin,
  rectIntersection,
  TouchSensor,
  useSensor,
  useSensors,
  type CollisionDetection,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { useMemo, useState } from "react";

import { KanbanColumn, type DragData } from "@/components/tickets/KanbanColumn";
import { TicketCard } from "@/components/tickets/TicketCard";
import { useFeed } from "@/context/FeedContext";
import { STATUSES } from "@/lib/constants";
import type { Status, TicketSummary } from "@/lib/types";

// Pointer position is the natural drop target for a mouse, but the keyboard
// sensor has no pointer, so fall back to rectangle overlap when there is none.
const collisionDetection: CollisionDetection = (args) => {
  const hits = pointerWithin(args);
  return hits.length > 0 ? hits : rectIntersection(args);
};

const RENDER_LIMIT: Record<Status, number> = { Open: 120, "In Progress": 120, Resolved: 40 };

interface KanbanBoardProps {
  tickets: TicketSummary[];
  onOpen: (ticketId: number) => void;
  onMove: (ticket: TicketSummary, status: Status) => void;
}

export function KanbanBoard({ tickets, onOpen, onMove }: KanbanBoardProps) {
  const { isFresh } = useFeed();
  const [dragging, setDragging] = useState<TicketSummary | null>(null);

  // Mouse and touch get separate sensors: a small movement threshold keeps a
  // click a click, and a press-and-hold on touch keeps a swipe a scroll.
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 220, tolerance: 8 } }),
    useSensor(KeyboardSensor, {
      keyboardCodes: { start: ["Space"], cancel: ["Escape"], end: ["Space", "Enter"] },
    }),
  );

  const columns = useMemo(() => {
    const grouped: Record<Status, TicketSummary[]> = { Open: [], "In Progress": [], Resolved: [] };
    for (const ticket of tickets) grouped[ticket.status].push(ticket);
    grouped.Resolved.sort((a, b) =>
      (b.resolved_at ?? b.updated_at).localeCompare(a.resolved_at ?? a.updated_at),
    );
    return grouped;
  }, [tickets]);

  const handleDragStart = (event: DragStartEvent) => {
    setDragging((event.active.data.current as DragData | undefined)?.ticket ?? null);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const ticket = (event.active.data.current as DragData | undefined)?.ticket;
    const target = event.over?.id as Status | undefined;
    setDragging(null);
    if (ticket && target && target !== ticket.status) onMove(ticket, target);
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={collisionDetection}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={() => setDragging(null)}
    >
      <div className="grid snap-x snap-mandatory auto-cols-[minmax(17rem,85vw)] grid-flow-col gap-3 overflow-x-auto pb-2 md:grid-flow-row md:auto-cols-auto md:grid-cols-3 md:overflow-visible">
        {STATUSES.map((status) => (
          <KanbanColumn
            key={status}
            status={status}
            tickets={columns[status]}
            limit={RENDER_LIMIT[status]}
            isFresh={isFresh}
            onOpen={onOpen}
          />
        ))}
      </div>

      <DragOverlay dropAnimation={{ duration: 180, easing: "cubic-bezier(0.22, 1, 0.36, 1)" }}>
        {dragging ? <TicketCard ticket={dragging} overlay /> : null}
      </DragOverlay>
    </DndContext>
  );
}
