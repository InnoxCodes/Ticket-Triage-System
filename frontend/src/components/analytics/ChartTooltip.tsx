interface TooltipEntry {
  name?: string | number;
  value?: unknown;
  color?: string;
  fill?: string;
  stroke?: string;
  payload?: unknown;
}

// Props are injected by Recharts when this is passed as `content`.
interface ChartTooltipProps {
  active?: boolean;
  payload?: readonly TooltipEntry[];
  label?: string | number;
  labelFormatter?: (label: string | number) => string;
  valueFormatter?: (value: number) => string;
  showTotal?: boolean;
  reversed?: boolean;
}

function swatch(entry: TooltipEntry): string | undefined {
  return entry.color ?? entry.fill ?? entry.stroke ?? (entry.payload as { fill?: string } | undefined)?.fill;
}

export function ChartTooltip({
  active,
  payload,
  label,
  labelFormatter,
  valueFormatter = (value) => value.toLocaleString(),
  showTotal = false,
  reversed = false,
}: ChartTooltipProps) {
  if (!active || !payload?.length) return null;

  const rows = payload.filter((entry) => typeof entry.value === "number");
  if (reversed) rows.reverse();
  const total = rows.reduce((sum, entry) => sum + (entry.value as number), 0);

  return (
    <div className="min-w-36 rounded-lg border border-line-strong bg-surface/95 px-3 py-2 text-xs shadow-overlay backdrop-blur">
      {label !== undefined && label !== "" && (
        <p className="mb-1.5 font-medium text-fg">{labelFormatter ? labelFormatter(label) : label}</p>
      )}
      <ul className="space-y-1">
        {rows.map((entry) => (
          <li key={String(entry.name)} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-fg-muted">
              <span className="size-2 rounded-full" style={{ background: swatch(entry) }} />
              {String(entry.name)}
            </span>
            <span className="font-mono tabular-nums text-fg">{valueFormatter(entry.value as number)}</span>
          </li>
        ))}
      </ul>
      {showTotal && rows.length > 1 && (
        <p className="mt-1.5 flex justify-between border-t border-line pt-1.5 text-fg-muted">
          <span>Total</span>
          <span className="font-mono tabular-nums text-fg">{valueFormatter(total)}</span>
        </p>
      )}
    </div>
  );
}
