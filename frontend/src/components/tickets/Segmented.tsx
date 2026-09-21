import { motion } from "framer-motion";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface SegmentedProps<T extends string> {
  label: string;
  options: readonly T[];
  value: T;
  onChange: (value: T) => void;
  renderOption?: (option: T, selected: boolean) => ReactNode;
  // Marks the model's original prediction, so the agent can see what they
  // are overriding without it being the selected value.
  aiValue?: T;
  disabled?: boolean;
  className?: string;
}

export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  renderOption,
  aiValue,
  disabled = false,
  className,
}: SegmentedProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn("grid gap-1 rounded-lg border border-line bg-surface-2 p-1", className)}
    >
      {options.map((option) => {
        const selected = option === value;

        return (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => {
              if (!selected) onChange(option);
            }}
            className={cn(
              "relative flex h-8 min-w-0 items-center justify-center gap-1.5 rounded-md px-2 text-xs font-medium transition-colors disabled:opacity-60",
              selected ? "text-fg" : "text-fg-muted hover:text-fg",
            )}
          >
            {selected && (
              <motion.span
                layoutId={`segmented-${label}`}
                className="absolute inset-0 rounded-md border border-line bg-surface shadow-panel"
                transition={{ type: "spring", stiffness: 500, damping: 38 }}
              />
            )}
            <span className="relative flex min-w-0 items-center gap-1.5 truncate">
              {renderOption ? renderOption(option, selected) : option}
            </span>
            {aiValue === option && (
              <span
                className="absolute right-1 top-1 size-1.5 rounded-full bg-accent"
                title="Model's original prediction"
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
