import type { ComponentProps } from "react";

import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/utils";

const VARIANTS = {
  primary:
    "bg-accent text-accent-fg shadow-[inset_0_1px_0_rgb(255_255_255/0.14)] hover:bg-accent-hover",
  secondary: "border border-line bg-surface-2 text-fg hover:border-line-strong hover:bg-surface-3",
  outline: "border border-line bg-transparent text-fg hover:bg-surface-2",
  ghost: "text-fg-muted hover:bg-surface-2 hover:text-fg",
  danger: "border border-critical/25 bg-critical-soft text-critical hover:bg-critical/15",
} as const;

const SIZES = {
  sm: "h-8 gap-1.5 px-2.5 text-xs [&_svg]:size-3.5",
  md: "h-9 gap-2 px-3.5 text-sm [&_svg]:size-4",
  lg: "h-11 gap-2 px-5 text-sm [&_svg]:size-4",
  icon: "size-9 [&_svg]:size-4",
  "icon-sm": "size-8 [&_svg]:size-4",
} as const;

export interface ButtonProps extends ComponentProps<"button"> {
  variant?: keyof typeof VARIANTS;
  size?: keyof typeof SIZES;
  loading?: boolean;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  disabled,
  className,
  children,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex shrink-0 select-none items-center justify-center whitespace-nowrap rounded-lg font-medium",
        "transition-[background-color,border-color,color,transform] duration-150 active:scale-[0.98]",
        "disabled:pointer-events-none disabled:opacity-50 [&_svg]:shrink-0",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
}
