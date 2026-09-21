import { cn } from "@/lib/utils";

export function Logo({ className, wordmark = true }: { className?: string; wordmark?: boolean }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <span className="grid size-7 place-items-center rounded-lg bg-linear-to-br from-accent to-cat-technical shadow-[0_6px_18px_-6px_var(--accent)]">
        <svg
          viewBox="0 0 24 24"
          className="size-4 text-white"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <path d="M3 12.5h3.5L9 7l4 10 2.5-4.5H21" />
        </svg>
      </span>
      {wordmark && (
        <span className="text-[15px] font-semibold tracking-tight text-fg">
          Triage<span className="text-accent">AI</span>
        </span>
      )}
    </span>
  );
}
