import type { TokenContribution } from "@/lib/types";
import { cn } from "@/lib/utils";

// Placeholder tokens produced by the backend's entity masking, shown as what
// they stand for rather than as internal vocabulary.
const MASKED_TOKENS: Record<string, string> = {
  moneyamt: "$ amount",
  refnum: "reference #",
  emailaddr: "email address",
  urladdr: "URL",
  ipaddr: "IP address",
  datestr: "date",
  timestr: "time",
  longnum: "long number",
};

export function readableTerm(term: string): string {
  return term
    .split(" ")
    .map((word) => MASKED_TOKENS[word] ?? word)
    .join(" ");
}

interface RationaleProps {
  terms: TokenContribution[];
  limit?: number;
  className?: string;
}

export function Rationale({ terms, limit = 6, className }: RationaleProps) {
  const shown = terms.filter((term) => term.weight > 0).slice(0, limit);

  if (shown.length === 0) {
    return (
      <p className={cn("text-xs text-fg-subtle", className)}>
        No single phrase stood out — the model leaned on its prior for this one.
      </p>
    );
  }

  const strongest = Math.max(...shown.map((term) => term.weight));

  return (
    <ul className={cn("flex flex-wrap gap-1.5", className)} aria-label="Phrases that drove the prediction">
      {shown.map((term) => (
        <li
          key={term.term}
          className="relative overflow-hidden rounded-md border border-line bg-surface-2 px-2 py-1 text-[11px]"
          title={`Contribution ${term.weight.toFixed(3)}`}
        >
          <span
            aria-hidden
            className="absolute inset-y-0 left-0 bg-accent-soft"
            style={{ width: `${(term.weight / strongest) * 100}%` }}
          />
          <span className="relative font-mono text-fg">{readableTerm(term.term)}</span>
        </li>
      ))}
    </ul>
  );
}
