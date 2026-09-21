import {
  Bug,
  CreditCard,
  KeyRound,
  Lightbulb,
  MessageCircleQuestionMark,
  Server,
} from "lucide-react";
import type { ComponentType } from "react";

import { CATEGORY_TONE } from "@/lib/constants";
import type { Category } from "@/lib/types";
import { cn } from "@/lib/utils";

export const CATEGORY_ICON: Record<Category, ComponentType<{ className?: string }>> = {
  Billing: CreditCard,
  "Bug Report": Bug,
  "Login/Access": KeyRound,
  "Feature Request": Lightbulb,
  "General Inquiry": MessageCircleQuestionMark,
  "Technical Issue": Server,
};

interface CategoryTagProps {
  category: Category;
  compact?: boolean;
  uncertain?: boolean;
  className?: string;
}

export function CategoryTag({ category, compact = false, uncertain = false, className }: CategoryTagProps) {
  const tone = CATEGORY_TONE[category];
  const Icon = CATEGORY_ICON[category];

  return (
    <span
      className={cn(
        "inline-flex h-5 shrink-0 items-center gap-1 rounded-md border px-1.5 text-[11px] font-medium",
        tone.soft,
        tone.text,
        uncertain ? "border-dashed border-current/45" : tone.border,
        className,
      )}
      title={uncertain ? `${category} (low model confidence)` : category}
    >
      <Icon className="size-3" aria-hidden />
      {compact ? tone.short : category}
    </span>
  );
}
