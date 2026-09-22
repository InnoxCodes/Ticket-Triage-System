import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ChartTooltip } from "@/components/analytics/ChartTooltip";
import { UrgencyDot } from "@/components/ui/UrgencyBadge";
import { useChartColors } from "@/hooks/useChartColors";
import { URGENCIES } from "@/lib/constants";
import type { TimeBucket, Urgency } from "@/lib/types";

const DATA_KEY: Record<Urgency, keyof TimeBucket> = {
  Critical: "critical",
  High: "high",
  Medium: "medium",
  Low: "low",
};

const formatDay = (date: string | number) =>
  new Date(`${date}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });

export function VolumeChart({ data }: { data: TimeBucket[] }) {
  const colors = useChartColors();
  // Stack least severe at the bottom so Critical sits on top, where the eye lands first.
  const layers = [...URGENCIES].reverse();

  return (
    <div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -18 }}>
            <defs>
              {layers.map((urgency) => (
                <linearGradient key={urgency} id={`volume-${urgency}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={colors.urgency[urgency]} stopOpacity={0.42} />
                  <stop offset="100%" stopColor={colors.urgency[urgency]} stopOpacity={0.04} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid vertical={false} stroke={colors.line} strokeDasharray="3 4" />
            <XAxis
              dataKey="date"
              tickFormatter={formatDay}
              tickLine={false}
              axisLine={false}
              minTickGap={28}
              tick={{ fill: colors.subtle, fontSize: 11 }}
            />
            <YAxis
              allowDecimals={false}
              tickLine={false}
              axisLine={false}
              width={40}
              tick={{ fill: colors.subtle, fontSize: 11 }}
            />
            <Tooltip
              cursor={{ stroke: colors.lineStrong }}
              content={<ChartTooltip labelFormatter={formatDay} showTotal reversed />}
            />
            {layers.map((urgency) => (
              <Area
                key={urgency}
                type="monotone"
                dataKey={DATA_KEY[urgency]}
                name={urgency}
                stackId="volume"
                stroke={colors.urgency[urgency]}
                strokeWidth={1.5}
                fill={`url(#volume-${urgency})`}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        {URGENCIES.map((urgency) => (
          <li key={urgency} className="flex items-center gap-1.5 text-[11px] text-fg-muted">
            <UrgencyDot urgency={urgency} pulse={false} />
            {urgency}
          </li>
        ))}
      </ul>
    </div>
  );
}
