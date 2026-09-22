import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { CircleAlert, Clock, Flame, Inbox, ScanSearch, Timer, Zap } from "lucide-react";
import { useState } from "react";

import { CategoryDonut } from "@/components/analytics/CategoryDonut";
import { ChartCard } from "@/components/analytics/ChartCard";
import { KpiTile } from "@/components/analytics/KpiTile";
import { ModelPerformance } from "@/components/analytics/ModelPerformance";
import { ReliabilityCard } from "@/components/analytics/ReliabilityCard";
import { UrgencyBars } from "@/components/analytics/UrgencyBars";
import { VolumeChart } from "@/components/analytics/VolumeChart";
import { Segmented } from "@/components/tickets/Segmented";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useFeed } from "@/context/FeedContext";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query";
import type { AnalyticsSummary } from "@/lib/types";
import { formatMinutes } from "@/lib/utils";

const RANGES = ["7d", "14d", "30d"] as const;
type Range = (typeof RANGES)[number];

function AnalyticsSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-label="Loading analytics">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-28 rounded-2xl" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-80 rounded-2xl lg:col-span-2" />
        <Skeleton className="h-80 rounded-2xl" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-72 rounded-2xl" />
        <Skeleton className="h-72 rounded-2xl lg:col-span-2" />
      </div>
    </div>
  );
}

function Overview({ summary, days }: { summary: AnalyticsSummary; days: number }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <KpiTile
          index={0}
          label="Tickets"
          value={summary.total_tickets.toLocaleString()}
          hint={`${summary.open_tickets + summary.in_progress_tickets} still active`}
          icon={Inbox}
          tone="bg-accent-soft text-accent"
        />
        <KpiTile
          index={1}
          label="Median resolution"
          value={formatMinutes(summary.median_resolution_minutes)}
          hint={`mean ${formatMinutes(summary.avg_resolution_minutes)}, skewed by slow tickets`}
          icon={Clock}
          tone="bg-cat-technical/10 text-cat-technical"
        />
        <KpiTile
          index={2}
          label="Critical, unresolved"
          value={String(summary.critical_open)}
          hint="need a human now"
          icon={Flame}
          tone="bg-critical-soft text-critical"
        />
        <KpiTile
          index={3}
          label="SLA breached"
          value={String(summary.sla_breached)}
          hint="past first-response target"
          icon={Timer}
          tone="bg-high-soft text-high"
        />
        <KpiTile
          index={4}
          label="Flagged for review"
          value={String(summary.needs_review_tickets)}
          hint="below confidence threshold"
          icon={ScanSearch}
          tone="bg-medium-soft text-medium"
        />
        <KpiTile
          index={5}
          label="Inference time"
          value={`${summary.avg_inference_ms.toFixed(1)}ms`}
          hint="per ticket, on CPU"
          icon={Zap}
          tone="bg-low-soft text-low"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard
          index={1}
          className="lg:col-span-2"
          title="Ticket volume"
          description={`New tickets per day over the last ${days} days, stacked by urgency.`}
        >
          <VolumeChart data={summary.volume_over_time} />
        </ChartCard>
        <ChartCard index={2} title="By category" description="What customers are writing in about.">
          <CategoryDonut data={summary.by_category} />
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard index={3} title="By urgency" description="Current urgency, after agent corrections.">
          <UrgencyBars data={summary.by_urgency} />
        </ChartCard>
        <ChartCard
          index={4}
          className="lg:col-span-2"
          title="AI reliability"
          description="How often agents disagree with the model on live traffic — something offline accuracy can't tell you."
        >
          <ReliabilityCard stats={summary.overrides} />
        </ChartCard>
      </div>
    </>
  );
}

export default function AnalyticsPage() {
  const { status } = useFeed();
  const [range, setRange] = useState<Range>("14d");
  const days = Number.parseInt(range, 10);

  const summary = useQuery({
    queryKey: queryKeys.analytics(days),
    queryFn: () => api.analytics(days),
    placeholderData: keepPreviousData,
    // Live feed events already invalidate this; polling only covers a dropped socket.
    refetchInterval: status === "live" ? false : 30_000,
  });

  const model = useQuery({
    queryKey: queryKeys.model,
    queryFn: api.modelPerformance,
    staleTime: Number.POSITIVE_INFINITY,
  });

  return (
    <div className="mx-auto max-w-[1600px] space-y-5 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium text-fg-subtle">Insights</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Analytics</h1>
          <p className="mt-1 text-sm text-fg-muted">How the queue is moving, and how far to trust the model.</p>
        </div>
        <Segmented label="Range" options={RANGES} value={range} onChange={setRange} className="w-48 grid-cols-3" />
      </header>

      {summary.isPending ? (
        <AnalyticsSkeleton />
      ) : summary.isError ? (
        <EmptyState
          icon={CircleAlert}
          title="Couldn't load analytics"
          description={summary.error.message}
          action={
            <Button size="sm" onClick={() => void summary.refetch()}>
              Try again
            </Button>
          }
          className="rounded-2xl border border-line bg-surface"
        />
      ) : (
        <Overview summary={summary.data} days={days} />
      )}

      <ChartCard
        index={5}
        title="Model performance"
        description={
          model.data
            ? `Offline evaluation on ${model.data.dataset.test} held-out tickets from the last training run.`
            : "Offline evaluation from the last training run."
        }
      >
        {model.isPending ? (
          <Skeleton className="h-96 rounded-xl" />
        ) : model.isError ? (
          <EmptyState compact icon={CircleAlert} title="Model metrics unavailable" description={model.error.message} />
        ) : (
          <ModelPerformance data={model.data} />
        )}
      </ChartCard>
    </div>
  );
}
