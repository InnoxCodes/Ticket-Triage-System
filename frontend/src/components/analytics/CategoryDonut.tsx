import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { ChartTooltip } from "@/components/analytics/ChartTooltip";
import { useChartColors } from "@/hooks/useChartColors";
import { CATEGORY_TONE } from "@/lib/constants";
import type { Category, CountBucket } from "@/lib/types";
import { cn, formatPercent } from "@/lib/utils";

export function CategoryDonut({ data }: { data: CountBucket[] }) {
  const colors = useChartColors();
  const total = data.reduce((sum, bucket) => sum + bucket.count, 0);
  const ranked = [...data].sort((a, b) => b.count - a.count);

  return (
    <div className="flex flex-col items-center gap-6 sm:flex-row lg:flex-col 2xl:flex-row">
      <div className="relative size-44 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="count"
              nameKey="label"
              innerRadius="70%"
              outerRadius="100%"
              paddingAngle={2}
              cornerRadius={4}
              startAngle={90}
              endAngle={-270}
              stroke="none"
            >
              {data.map((bucket) => (
                <Cell key={bucket.label} fill={colors.category[bucket.label as Category]} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
          <div>
            <p className="font-mono text-2xl font-semibold tabular-nums">{total}</p>
            <p className="text-[11px] text-fg-subtle">tickets</p>
          </div>
        </div>
      </div>

      <ul className="w-full min-w-0 space-y-2">
        {ranked.map((bucket) => (
          <li key={bucket.label} className="flex items-center gap-2.5 text-xs">
            <span className={cn("size-2 shrink-0 rounded-full", CATEGORY_TONE[bucket.label as Category]?.dot)} />
            <span className="min-w-0 flex-1 truncate text-fg-muted">{bucket.label}</span>
            <span className="font-mono tabular-nums">{bucket.count}</span>
            <span className="w-10 text-right font-mono tabular-nums text-fg-subtle">
              {total ? formatPercent(bucket.count / total) : "0%"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
