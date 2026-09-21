import type { ComponentProps, ComponentType, ReactNode } from "react";

import { cn } from "@/lib/utils";

const FIELD =
  "w-full rounded-lg border border-line bg-surface text-sm text-fg placeholder:text-fg-subtle outline-none " +
  "transition-[border-color,box-shadow] duration-150 hover:border-line-strong " +
  "focus:border-accent/60 focus:ring-4 focus:ring-accent/15 " +
  "aria-[invalid=true]:border-critical/60 aria-[invalid=true]:focus:ring-critical/15 disabled:opacity-60";

interface InputProps extends ComponentProps<"input"> {
  icon?: ComponentType<{ className?: string }>;
  trailing?: ReactNode;
}

export function Input({ icon: Icon, trailing, className, ...props }: InputProps) {
  return (
    <div className="relative">
      {Icon && (
        <Icon
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-subtle"
          aria-hidden
        />
      )}
      <input
        className={cn(FIELD, "h-10 px-3", Icon && "pl-9", trailing && "pr-10", className)}
        {...props}
      />
      {trailing && <div className="absolute right-1.5 top-1/2 -translate-y-1/2">{trailing}</div>}
    </div>
  );
}

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return (
    <textarea
      className={cn(FIELD, "min-h-36 resize-y px-3 py-2.5 leading-relaxed", className)}
      {...props}
    />
  );
}

export function FieldLabel({ className, ...props }: ComponentProps<"label">) {
  return (
    <label className={cn("mb-1.5 block text-xs font-medium text-fg-muted", className)} {...props} />
  );
}

export function FieldError({ id, children }: { id?: string; children?: ReactNode }) {
  if (!children) return null;
  return (
    <p id={id} role="alert" className="mt-1.5 text-xs text-critical">
      {children}
    </p>
  );
}
