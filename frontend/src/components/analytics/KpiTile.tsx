import { motion } from "framer-motion";
import type { ComponentType } from "react";

import { cn } from "@/lib/utils";

interface KpiTileProps {
  label: string;
  value: string;
  hint?: string;
  icon: ComponentType<{ className?: string }>;
  tone: string;
  index?: number;
}

export function KpiTile({ label, value, hint, icon: Icon, tone, index = 0 }: KpiTileProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.04 * index, ease: [0.22, 1, 0.36, 1] }}
      className="min-w-0 rounded-2xl border border-line bg-surface p-4 shadow-panel"
    >
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-xs text-fg-muted">{label}</p>
        <span className={cn("grid size-7 shrink-0 place-items-center rounded-lg", tone)}>
          <Icon className="size-3.5" />
        </span>
      </div>
      <p className="mt-3 font-mono text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      {hint && <p className="mt-1 truncate text-[11px] text-fg-subtle">{hint}</p>}
    </motion.div>
  );
}
