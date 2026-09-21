import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  ArrowUpRight,
  CircleAlert,
  Flame,
  Inbox,
  ScanSearch,
  Search,
  Timer,
  X,
} from "lucide-react";
import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import { Link, useSearchParams } from "react-router-dom";

import { KanbanBoard } from "@/components/tickets/KanbanBoard";
import { SimulatorToggle } from "@/components/tickets/SimulatorToggle";
import { TicketDrawer } from "@/components/tickets/TicketDrawer";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { UrgencyDot } from "@/components/ui/UrgencyBadge";
import { FALLBACK_POLL_MS, useFeed } from "@/context/FeedContext";
import { useUpdateTicket } from "@/hooks/useUpdateTicket";
import { api } from "@/lib/api";
import { CATEGORIES, URGENCIES } from "@/lib/constants";
import { BOARD_QUERY, queryKeys } from "@/lib/query";
import type { Category, Status, TicketSummary, Urgency } from "@/lib/types";
import { cn } from "@/lib/utils";

const EASE = [0.22, 1, 0.36, 1] as const;

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

interface QueueStatProps {
  label: string;
  value: number;
  icon: ComponentType<{ className?: string }>;
  tone: string;
  index: number;
}

function QueueStat({ label, value, icon: Icon, tone, index }: QueueStatProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 * index, duration: 0.4, ease: EASE }}
      className="flex items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3 shadow-panel"
    >
      <span className={cn("grid size-9 shrink-0 place-items-center rounded-lg", tone)}>
        <Icon className="size-4" />
      </span>
      <div className="min-w-0">
        <p className="font-mono text-xl font-semibold leading-none tracking-tight tabular-nums">
          {value}
        </p>
        <p className="mt-1 truncate text-xs text-fg-muted">{label}</p>
      </div>
    </motion.div>
  );
}

function Chip({
  active,
  onClick,
  title,
  children,
}: {
  active: boolean;
  onClick: () => void;
  title?: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      title={title}
      className={cn(
        "inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border px-2.5 text-xs font-medium transition-colors",
        active
          ? "border-accent/40 bg-accent-soft text-fg"
          : "border-line bg-surface text-fg-muted hover:border-line-strong hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

function BoardSkeleton() {
  return (
    <div className="grid gap-3 md:grid-cols-3" role="status" aria-label="Loading tickets">
      {[4, 3, 2].map((cards, column) => (
        <div key={column} className="space-y-2.5 rounded-2xl border border-line bg-surface-2/40 p-3">
          <Skeleton className="h-4 w-24" />
          {Array.from({ length: cards }, (_, index) => (
            <Skeleton key={index} className="h-30 rounded-xl" />
          ))}
        </div>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const { status: feedStatus } = useFeed();
  const { mutate: updateTicket } = useUpdateTicket();
  const [params, setParams] = useSearchParams();

  const [search, setSearch] = useState("");
  const [urgencies, setUrgencies] = useState<ReadonlySet<Urgency>>(() => new Set());
  const [category, setCategory] = useState<Category | "all">("all");
  const [reviewOnly, setReviewOnly] = useState(false);
  const deferredSearch = useDeferredValue(search);
  const searchRef = useRef<HTMLInputElement>(null);

  const board = useQuery({
    queryKey: queryKeys.board,
    queryFn: () => api.listTickets(BOARD_QUERY),
    // The socket pushes changes while it is up; polling only covers the gaps.
    refetchInterval: feedStatus === "live" ? false : FALLBACK_POLL_MS,
  });

  const openId = Number(params.get("ticket")) || null;

  const openTicket = useCallback(
    (ticketId: number) =>
      setParams((previous) => {
        const next = new URLSearchParams(previous);
        next.set("ticket", String(ticketId));
        return next;
      }),
    [setParams],
  );

  const closeTicket = useCallback(
    () =>
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          next.delete("ticket");
          return next;
        },
        { replace: true },
      ),
    [setParams],
  );

  const moveTicket = useCallback(
    (ticket: TicketSummary, status: Status) => updateTicket({ ticket, patch: { status } }),
    [updateTicket],
  );

  useEffect(() => {
    const focusSearch = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable='true']")) return;
      event.preventDefault();
      searchRef.current?.focus();
    };
    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);

  const items = useMemo(() => board.data?.items ?? [], [board.data]);

  const stats = useMemo(() => {
    const active = items.filter((ticket) => ticket.status !== "Resolved");
    return {
      active: active.length,
      critical: active.filter((ticket) => ticket.urgency === "Critical").length,
      review: active.filter((ticket) => ticket.ai_needs_review && !ticket.was_overridden).length,
      breached: active.filter((ticket) => ticket.sla_breached).length,
    };
  }, [items]);

  const filtersActive = urgencies.size > 0 || category !== "all" || reviewOnly || search.trim() !== "";

  const filtered = useMemo(() => {
    const needle = deferredSearch.trim().toLowerCase();
    return items.filter((ticket) => {
      if (urgencies.size > 0 && !urgencies.has(ticket.urgency)) return false;
      if (category !== "all" && ticket.category !== category) return false;
      if (reviewOnly && !(ticket.ai_needs_review && !ticket.was_overridden)) return false;
      if (needle) {
        const haystack = `${ticket.reference} ${ticket.subject} ${ticket.preview}`.toLowerCase();
        if (!haystack.includes(needle)) return false;
      }
      return true;
    });
  }, [items, urgencies, category, reviewOnly, deferredSearch]);

  const toggleUrgency = (urgency: Urgency) =>
    setUrgencies((previous) => {
      const next = new Set(previous);
      if (next.has(urgency)) next.delete(urgency);
      else next.add(urgency);
      return next;
    });

  const clearFilters = () => {
    setSearch("");
    setUrgencies(new Set());
    setCategory("all");
    setReviewOnly(false);
  };

  const openSummary = openId ? items.find((ticket) => ticket.id === openId) : undefined;

  return (
    <div className="mx-auto max-w-[1600px] space-y-5 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium text-fg-subtle">{greeting()}</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Support queue</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SimulatorToggle />
          <Link
            to="/submit"
            target="_blank"
            rel="noreferrer"
            title="Opens the customer form in a new tab, so you can watch the ticket arrive here"
            className="inline-flex h-9 items-center gap-2 rounded-lg bg-accent px-3.5 text-sm font-medium text-accent-fg shadow-[inset_0_1px_0_rgb(255_255_255/0.14)] transition-colors hover:bg-accent-hover"
          >
            New ticket
            <ArrowUpRight className="size-4" />
          </Link>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <QueueStat index={0} label="Active tickets" value={stats.active} icon={Inbox} tone="bg-accent-soft text-accent" />
        <QueueStat index={1} label="Critical, unresolved" value={stats.critical} icon={Flame} tone="bg-critical-soft text-critical" />
        <QueueStat index={2} label="Awaiting human review" value={stats.review} icon={ScanSearch} tone="bg-medium-soft text-medium" />
        <QueueStat index={3} label="Past first-response SLA" value={stats.breached} icon={Timer} tone="bg-high-soft text-high" />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-subtle" aria-hidden />
          <input
            ref={searchRef}
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search tickets"
            aria-label="Search tickets"
            className="h-8 w-full rounded-lg border border-line bg-surface pl-9 pr-9 text-xs text-fg outline-none transition-colors placeholder:text-fg-subtle hover:border-line-strong focus:border-accent/60 focus:ring-4 focus:ring-accent/15"
          />
          <kbd className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-line bg-surface-2 px-1.5 font-mono text-[10px] text-fg-subtle">
            /
          </kbd>
        </div>

        <div className="flex max-w-full items-center gap-1.5 overflow-x-auto scrollbar-none">
          {URGENCIES.map((urgency) => (
            <Chip key={urgency} active={urgencies.has(urgency)} onClick={() => toggleUrgency(urgency)}>
              <UrgencyDot urgency={urgency} pulse={false} />
              {urgency}
            </Chip>
          ))}
        </div>

        <select
          value={category}
          onChange={(event) => setCategory(event.target.value as Category | "all")}
          aria-label="Filter by category"
          className={cn(
            "h-8 rounded-lg border bg-surface px-2.5 text-xs font-medium outline-none transition-colors hover:border-line-strong focus:border-accent/60",
            category === "all" ? "border-line text-fg-muted" : "border-accent/40 text-fg",
          )}
        >
          <option value="all">All categories</option>
          {CATEGORIES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>

        <Chip
          active={reviewOnly}
          onClick={() => setReviewOnly((value) => !value)}
          title="Tickets where the model's confidence fell below the review threshold"
        >
          <ScanSearch className="size-3.5" />
          Needs review
          <span className="font-mono text-fg-subtle">{stats.review}</span>
        </Chip>

        {filtersActive && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            <X />
            Clear
          </Button>
        )}

        {board.isFetching && !board.isPending && (
          <span className="ml-auto hidden text-[11px] text-fg-subtle sm:inline">Syncing…</span>
        )}
      </div>

      {board.isPending ? (
        <BoardSkeleton />
      ) : board.isError ? (
        <EmptyState
          icon={CircleAlert}
          title="Couldn't load the queue"
          description={board.error.message}
          action={
            <Button size="sm" onClick={() => void board.refetch()}>
              Try again
            </Button>
          }
          className="rounded-2xl border border-line bg-surface"
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="No tickets yet"
          description="Submit one from the customer form, or start the traffic simulator and watch tickets arrive live."
          action={<SimulatorToggle />}
          className="rounded-2xl border border-line bg-surface"
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Search}
          title="Nothing matches these filters"
          description="Try a broader search, or clear the filters to see the whole queue."
          action={
            <Button size="sm" onClick={clearFilters}>
              Clear filters
            </Button>
          }
          className="rounded-2xl border border-line bg-surface"
        />
      ) : (
        <KanbanBoard tickets={filtered} onOpen={openTicket} onMove={moveTicket} />
      )}

      <TicketDrawer ticketId={openId} summary={openSummary} onClose={closeTicket} />
    </div>
  );
}
