import { useMemo } from "react";

import { useTheme } from "@/context/ThemeContext";
import { CATEGORIES, CATEGORY_TONE, URGENCIES, URGENCY_TONE } from "@/lib/constants";
import type { Category, Urgency } from "@/lib/types";

export interface ChartColors {
  accent: string;
  fg: string;
  muted: string;
  subtle: string;
  line: string;
  lineStrong: string;
  surface: string;
  surface2: string;
  urgency: Record<Urgency, string>;
  category: Record<Category, string>;
}

// Recharts needs literal colour values, not classes, so resolve the CSS tokens
// and recompute whenever the theme flips.
export function useChartColors(): ChartColors {
  const { theme } = useTheme();

  return useMemo(() => {
    const style = getComputedStyle(document.documentElement);
    const read = (name: string) => style.getPropertyValue(name).trim();

    return {
      accent: read("--accent"),
      fg: read("--fg"),
      muted: read("--fg-muted"),
      subtle: read("--fg-subtle"),
      line: read("--line"),
      lineStrong: read("--line-strong"),
      surface: read("--surface"),
      surface2: read("--surface-2"),
      urgency: Object.fromEntries(
        URGENCIES.map((urgency) => [urgency, read(URGENCY_TONE[urgency].cssVar)]),
      ) as Record<Urgency, string>,
      category: Object.fromEntries(
        CATEGORIES.map((category) => [category, read(CATEGORY_TONE[category].cssVar)]),
      ) as Record<Category, string>,
    };
    // `theme` is the trigger: the tokens are read from the DOM, not from it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme]);
}
