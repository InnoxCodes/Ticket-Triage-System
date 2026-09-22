import { formatPercent } from "@/lib/utils";

interface ConfusionMatrixProps {
  labels: string[];
  matrix: number[][];
  shortLabel?: (label: string) => string;
}

export function ConfusionMatrix({ labels, matrix, shortLabel = (label) => label }: ConfusionMatrixProps) {
  return (
    <div className="overflow-x-auto">
      <div className="min-w-[22rem]">
        <p className="mb-1 pl-24 text-center text-[10px] font-medium uppercase tracking-[0.08em] text-fg-subtle">
          Predicted
        </p>
        <div
          className="grid gap-1"
          style={{ gridTemplateColumns: `6rem repeat(${labels.length}, minmax(0, 1fr))` }}
        >
          <span className="self-end pb-1 text-[10px] font-medium uppercase tracking-[0.08em] text-fg-subtle">
            Actual
          </span>
          {labels.map((label) => (
            <span key={label} title={label} className="truncate pb-1 text-center text-[10.5px] text-fg-muted">
              {shortLabel(label)}
            </span>
          ))}

          {labels.map((actual, rowIndex) => {
            const row = matrix[rowIndex] ?? [];
            const rowTotal = row.reduce((sum, value) => sum + value, 0);

            return [
              <span
                key={`${actual}-label`}
                title={actual}
                className="flex items-center truncate pr-2 text-[10.5px] text-fg-muted"
              >
                {shortLabel(actual)}
              </span>,
              ...labels.map((predicted, columnIndex) => {
                const count = row[columnIndex] ?? 0;
                // Shade by share of the actual class, not raw count, so a
                // small class's errors are as visible as a large class's.
                const share = rowTotal ? count / rowTotal : 0;
                const correct = rowIndex === columnIndex;
                const strength = Math.round(14 + share * 66);

                return (
                  <span
                    key={`${actual}-${predicted}`}
                    title={`Actual ${actual} → predicted ${predicted}: ${count} (${formatPercent(share)})`}
                    className={`grid min-h-8 place-items-center rounded-md font-mono text-[11px] tabular-nums ${count === 0 ? "text-fg-subtle/50" : "text-fg"}`}
                    style={{
                      backgroundColor:
                        count === 0
                          ? "var(--surface-2)"
                          : `color-mix(in oklab, var(${correct ? "--accent" : "--critical"}) ${strength}%, var(--surface-2))`,
                    }}
                  >
                    {count}
                  </span>
                );
              }),
            ];
          })}
        </div>
      </div>
    </div>
  );
}
