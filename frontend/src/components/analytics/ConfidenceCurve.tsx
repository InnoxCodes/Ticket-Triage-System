import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ChartTooltip } from "@/components/analytics/ChartTooltip";
import { useChartColors } from "@/hooks/useChartColors";
import type { ConfidencePoint } from "@/lib/types";
import { formatPercent } from "@/lib/utils";

const percent = (value: number) => formatPercent(value);

export function ConfidenceCurve({ curve, threshold }: { curve: ConfidencePoint[]; threshold: number }) {
  const colors = useChartColors();

  const series = [
    { key: "accuracy", name: "Accuracy on auto-routed", color: colors.accent, dashed: false },
    { key: "coverage", name: "Share auto-routed", color: colors.category["Technical Issue"], dashed: false },
    { key: "escalated_accuracy", name: "Accuracy on escalated", color: colors.subtle, dashed: true },
  ] as const;

  return (
    <div>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={curve} margin={{ top: 14, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid vertical={false} stroke={colors.line} strokeDasharray="3 4" />
            <XAxis
              dataKey="threshold"
              type="number"
              domain={["dataMin", "dataMax"]}
              ticks={curve.map((point) => point.threshold)}
              tickFormatter={percent}
              tickLine={false}
              axisLine={false}
              tick={{ fill: colors.subtle, fontSize: 10.5 }}
            />
            <YAxis
              domain={[0, 1]}
              tickFormatter={percent}
              tickLine={false}
              axisLine={false}
              width={44}
              tick={{ fill: colors.subtle, fontSize: 10.5 }}
            />
            <Tooltip
              cursor={{ stroke: colors.lineStrong }}
              content={
                <ChartTooltip
                  labelFormatter={(label) => `Threshold ${percent(Number(label))}`}
                  valueFormatter={percent}
                />
              }
            />
            <ReferenceLine
              x={threshold}
              stroke={colors.fg}
              strokeOpacity={0.45}
              strokeDasharray="4 4"
              label={{ value: "shipped", position: "insideTopLeft", fill: colors.muted, fontSize: 10 }}
            />
            {series.map((line) => (
              <Line
                key={line.key}
                type="monotone"
                dataKey={line.key}
                name={line.name}
                stroke={line.color}
                strokeWidth={2}
                strokeDasharray={line.dashed ? "5 4" : undefined}
                dot={{ r: 2.5, strokeWidth: 0, fill: line.color }}
                activeDot={{ r: 4 }}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        {series.map((line) => (
          <li key={line.key} className="flex items-center gap-1.5 text-[11px] text-fg-muted">
            <span className="h-0.5 w-3 rounded-full" style={{ background: line.color }} />
            {line.name}
          </li>
        ))}
      </ul>
    </div>
  );
}
