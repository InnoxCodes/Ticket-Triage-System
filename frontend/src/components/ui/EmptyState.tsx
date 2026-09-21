import type { ComponentType, ReactNode } from "react";

import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: ReactNode;
  compact?: boolean;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  compact = false,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center",
        compact ? "gap-2.5 px-4 py-8" : "gap-3 px-6 py-16",
        className,
      )}
    >
      <span className="relative grid size-11 place-items-center overflow-hidden rounded-2xl border border-line bg-surface-2 text-fg-subtle">
        <span aria-hidden className="absolute inset-0 bg-linear-to-b from-accent/15 to-transparent" />
        <Icon className="relative size-5" />
      </span>
      <div className="space-y-1">
        <p className="text-sm font-medium text-fg">{title}</p>
        {description && (
          <p className="mx-auto max-w-xs text-xs leading-relaxed text-fg-muted">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}
