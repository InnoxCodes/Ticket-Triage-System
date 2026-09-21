import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { CircleAlert, Clock, Mail, PenLine, RotateCcw, TriangleAlert, X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

import { Rationale } from "@/components/tickets/Rationale";
import { Segmented } from "@/components/tickets/Segmented";
import { Button } from "@/components/ui/Button";
import { CATEGORY_ICON, CategoryTag } from "@/components/ui/CategoryTag";
import { categoryBarTone, ConfidenceBars, urgencyBarTone } from "@/components/ui/ConfidenceBars";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { UrgencyBadge, UrgencyDot } from "@/components/ui/UrgencyBadge";
import { useNow } from "@/hooks/useNow";
import { useUpdateTicket } from "@/hooks/useUpdateTicket";
import { api } from "@/lib/api";
import {
  CATEGORIES,
  CATEGORY_TONE,
  REVIEW_THRESHOLD,
  STATUS_META,
  STATUSES,
  URGENCIES,
} from "@/lib/constants";
import { queryKeys } from "@/lib/query";
import type { LabelScore, TicketDetail, TicketSummary, TicketUpdate, TokenContribution } from "@/lib/types";
import {
  cn,
  formatDateTime,
  formatMinutes,
  formatPercent,
  slaMinutesRemaining,
  timeAgo,
} from "@/lib/utils";

function Section({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section>
      <div className="mb-2.5 flex items-center justify-between gap-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-subtle">{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  );
}

function SlaLine({ ticket, now }: { ticket: TicketDetail; now: number }) {
  if (ticket.status === "Resolved" && ticket.resolved_at) {
    const took =
      (new Date(ticket.resolved_at).getTime() - new Date(ticket.created_at).getTime()) / 60_000;
    return (
      <p className="mt-2 flex items-center gap-1.5 text-xs text-fg-muted">
        <Clock className="size-3.5" aria-hidden />
        Resolved in {formatMinutes(took)} · {ticket.sla_breached ? "missed" : "within"} the{" "}
        {formatMinutes(ticket.sla_minutes)} target
      </p>
    );
  }

  const remaining = slaMinutesRemaining(ticket.created_at, ticket.sla_minutes, now);
  return (
    <p className={cn("mt-2 flex items-center gap-1.5 text-xs", remaining < 0 ? "text-critical" : "text-fg-muted")}>
      <Clock className="size-3.5" aria-hidden />
      {remaining < 0
        ? `First response overdue by ${formatMinutes(-remaining)}`
        : `${formatMinutes(remaining)} left of the ${formatMinutes(ticket.sla_minutes)} ${ticket.urgency.toLowerCase()} target`}
    </p>
  );
}

interface PredictionBlockProps<T extends string> {
  title: string;
  aiLabel: T;
  current: T;
  confidence: number;
  threshold: number;
  scores: LabelScore[];
  rationale: TokenContribution[];
  toneFor: (label: string) => string;
  options: readonly T[];
  renderOption: (option: T) => ReactNode;
  gridClass: string;
  pending: boolean;
  onChange: (value: T) => void;
}

function PredictionBlock<T extends string>(props: PredictionBlockProps<T>) {
  const { title, aiLabel, current, confidence, threshold, onChange, pending } = props;
  const overridden = current !== aiLabel;
  const uncertain = !overridden && confidence < threshold;

  return (
    <Section
      title={title}
      aside={
        <span className={cn("font-mono text-[11px]", uncertain ? "text-medium" : "text-fg-subtle")}>
          model {formatPercent(confidence)} confident
        </span>
      }
    >
      {uncertain && (
        <p className="mb-3 flex items-start gap-2 rounded-lg border border-medium/25 bg-medium-soft px-3 py-2 text-xs leading-relaxed text-fg">
          <TriangleAlert className="mt-px size-3.5 shrink-0 text-medium" aria-hidden />
          Below the {formatPercent(threshold)} review threshold — worth a second look.
        </p>
      )}
      {overridden && (
        <p className="mb-3 flex items-start gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs leading-relaxed text-fg-muted">
          <PenLine className="mt-px size-3.5 shrink-0" aria-hidden />
          <span>
            Changed from the model's <span className="font-medium text-fg">{aiLabel}</span>. Logged
            to the reliability metrics.
          </span>
        </p>
      )}

      <ConfidenceBars
        scores={props.scores}
        toneFor={props.toneFor}
        highlight={aiLabel}
        threshold={threshold}
      />

      <p className="mb-1.5 mt-4 text-[11px] font-medium text-fg-subtle">What drove it</p>
      <Rationale terms={props.rationale} />

      <div className="mb-1.5 mt-4 flex items-center justify-between">
        <p className="text-[11px] font-medium text-fg-subtle">Your call</p>
        {overridden && (
          <button
            type="button"
            disabled={pending}
            onClick={() => onChange(aiLabel)}
            className="inline-flex items-center gap-1 text-[11px] text-fg-subtle transition-colors hover:text-fg disabled:opacity-50"
          >
            <RotateCcw className="size-3" aria-hidden />
            Restore model's call
          </button>
        )}
      </div>
      <Segmented
        label={title}
        options={props.options}
        value={current}
        aiValue={aiLabel}
        onChange={onChange}
        disabled={pending}
        className={props.gridClass}
        renderOption={props.renderOption}
      />
    </Section>
  );
}

function DrawerSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading ticket">
      <Skeleton className="h-28 rounded-xl" />
      <Skeleton className="h-10 rounded-lg" />
      <div className="space-y-2">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-3" />
        ))}
      </div>
      <Skeleton className="h-40 rounded-xl" />
    </div>
  );
}

function DrawerContent({
  ticketId,
  summary,
  onClose,
}: {
  ticketId: number;
  summary?: TicketSummary;
  onClose: () => void;
}) {
  const now = useNow();
  const update = useUpdateTicket();
  const query = useQuery({
    queryKey: queryKeys.ticket(ticketId),
    queryFn: ({ signal }) => api.getTicket(ticketId, signal),
  });

  const ticket = query.data;
  const head = ticket ?? summary;

  const change = (patch: TicketUpdate) => {
    if (ticket) update.mutate({ ticket, patch });
  };

  return (
    <>
      <header className="flex items-start gap-3 border-b border-line px-6 pb-4 pt-5">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 font-mono text-[11px] text-fg-subtle">
            <span>{head?.reference ?? "Loading…"}</span>
            {head && (
              <>
                <span aria-hidden>·</span>
                <time dateTime={head.created_at} title={formatDateTime(head.created_at)}>
                  {timeAgo(head.created_at, now)}
                </time>
              </>
            )}
          </div>
          {head ? (
            <h2 id="ticket-drawer-title" className="mt-1.5 text-lg font-semibold leading-snug tracking-tight">
              {head.subject}
            </h2>
          ) : (
            <Skeleton className="mt-2 h-6 w-3/4" />
          )}
          {head && (
            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
              <UrgencyBadge urgency={head.urgency} size="md" />
              <CategoryTag category={head.category} />
            </div>
          )}
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close ticket">
          <X />
        </Button>
      </header>

      <div className="flex-1 space-y-7 overflow-y-auto px-6 py-5">
        {query.isError ? (
          <EmptyState
            icon={CircleAlert}
            title="Couldn't load this ticket"
            description={query.error.message}
            action={
              <Button size="sm" onClick={() => void query.refetch()}>
                Try again
              </Button>
            }
          />
        ) : !ticket ? (
          <DrawerSkeleton />
        ) : (
          <>
            <Section
              title="Customer message"
              aside={
                ticket.requester_email && (
                  <a
                    href={`mailto:${ticket.requester_email}`}
                    className="inline-flex items-center gap-1 text-[11px] text-fg-muted hover:text-fg"
                  >
                    <Mail className="size-3" aria-hidden />
                    {ticket.requester_email}
                  </a>
                )
              }
            >
              <p className="whitespace-pre-wrap rounded-xl border border-line bg-surface-2/60 p-4 text-sm leading-relaxed">
                {ticket.body}
              </p>
            </Section>

            <Section title="Status">
              <Segmented
                label="Status"
                options={STATUSES}
                value={ticket.status}
                onChange={(status) => change({ status })}
                disabled={update.isPending}
                className="grid-cols-3"
                renderOption={(status) => (
                  <>
                    <span className={cn("size-1.5 rounded-full", STATUS_META[status].dot)} aria-hidden />
                    {status}
                  </>
                )}
              />
              <SlaLine ticket={ticket} now={now} />
            </Section>

            <PredictionBlock
              title="Urgency"
              aiLabel={ticket.ai_urgency}
              current={ticket.urgency}
              confidence={ticket.ai_urgency_confidence}
              threshold={REVIEW_THRESHOLD.urgency}
              scores={ticket.ai_urgency_scores}
              rationale={ticket.ai_urgency_rationale}
              toneFor={urgencyBarTone}
              options={URGENCIES}
              gridClass="grid-cols-4"
              pending={update.isPending}
              onChange={(urgency) => change({ urgency })}
              renderOption={(urgency) => (
                <>
                  <UrgencyDot urgency={urgency} pulse={false} />
                  {urgency}
                </>
              )}
            />

            <PredictionBlock
              title="Category"
              aiLabel={ticket.ai_category}
              current={ticket.category}
              confidence={ticket.ai_category_confidence}
              threshold={REVIEW_THRESHOLD.category}
              scores={ticket.ai_category_scores}
              rationale={ticket.ai_category_rationale}
              toneFor={categoryBarTone}
              options={CATEGORIES}
              gridClass="grid-cols-2 sm:grid-cols-3"
              pending={update.isPending}
              onChange={(category) => change({ category })}
              renderOption={(category) => {
                const Icon = CATEGORY_ICON[category];
                return (
                  <>
                    <Icon className={cn("size-3.5 shrink-0", CATEGORY_TONE[category].text)} />
                    {CATEGORY_TONE[category].short}
                  </>
                );
              }}
            />

            <Section title="Correction history">
              {ticket.overrides.length === 0 ? (
                <p className="text-xs text-fg-subtle">No corrections — the model's call stands.</p>
              ) : (
                <ol className="space-y-3">
                  {[...ticket.overrides].reverse().map((override) => (
                    <li key={override.id} className="flex gap-3 text-xs">
                      <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-surface-3 text-fg-muted">
                        <PenLine className="size-3" aria-hidden />
                      </span>
                      <div className="min-w-0 leading-relaxed">
                        <p>
                          <span className="font-medium capitalize">{override.field}</span>{" "}
                          <span className="text-fg-muted">changed</span>{" "}
                          <span className="text-fg-subtle line-through">{override.from_value}</span>
                          {" → "}
                          <span className="font-medium">{override.to_value}</span>
                        </p>
                        <p className="font-mono text-[10.5px] text-fg-subtle">
                          model was {formatPercent(override.model_confidence)} confident ·{" "}
                          {timeAgo(override.created_at, now)}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </Section>

            <p className="border-t border-line pt-4 font-mono text-[10.5px] text-fg-subtle">
              model {ticket.model_version.slice(0, 10)} · classified in {ticket.inference_ms.toFixed(1)}ms
            </p>
          </>
        )}
      </div>
    </>
  );
}

interface TicketDrawerProps {
  ticketId: number | null;
  summary?: TicketSummary;
  onClose: () => void;
}

export function TicketDrawer({ ticketId, summary, onClose }: TicketDrawerProps) {
  const open = ticketId !== null;
  const panelRef = useRef<HTMLElement>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;

    const returnFocusTo = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseRef.current();
    };

    document.addEventListener("keydown", handleKey);
    document.body.style.overflow = "hidden";
    panelRef.current?.focus();

    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = previousOverflow;
      returnFocusTo?.focus?.();
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="backdrop"
            aria-hidden
            className="fixed inset-0 z-50 bg-black/45 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            key="panel"
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="ticket-drawer-title"
            tabIndex={-1}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-line bg-surface shadow-overlay outline-none"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 40 }}
          >
            <DrawerContent key={ticketId} ticketId={ticketId} summary={summary} onClose={onClose} />
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
