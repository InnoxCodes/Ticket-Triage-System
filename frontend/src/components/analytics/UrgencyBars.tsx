import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ChartTooltip } from "@/components/analytics/ChartTooltip";
import { useChartColors } from "@/hooks/useChartColors";
import type { CountBucket, Urgency } from "@/lib/types";

export function UrgencyBars({ data }: { data: CountBucket[] }) {
  const colors = useChartColors();

  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -18 }}>
          <CartesianGrid vertical={false} stroke={colors.line} strokeDasharray="3 4" />
          <XAxis
            dataKey="label"
            tickLine={false}
            axisLine={false}
            tick={{ fill: colors.muted, fontSize: 11 }}
          />
          <YAxis
            allowDecimals={false}
            tickLine={false}
            axisLine={false}
            width={40}
            tick={{ fill: colors.subtle, fontSize: 11 }}
          />
          <Tooltip cursor={{ fill: colors.surface2 }} content={<ChartTooltip />} />
          <Bar dataKey="count" name="Tickets" radius={[6, 6, 2, 2]} maxBarSize={56}>
            {data.map((bucket) => (
              <Cell key={bucket.label} fill={colors.urgency[bucket.label as Urgency]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
