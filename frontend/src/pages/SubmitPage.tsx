import { useMutation } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowUpRight,
  Check,
  CircleAlert,
  CircleCheckBig,
  Mail,
  Moon,
  PenLine,
  ScanSearch,
  Send,
  Sparkles,
  Sun,
  TriangleAlert,
  WandSparkles,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { Rationale } from "@/components/tickets/Rationale";
import { Button } from "@/components/ui/Button";
import { CategoryTag } from "@/components/ui/CategoryTag";
import { categoryBarTone, ConfidenceBars, urgencyBarTone } from "@/components/ui/ConfidenceBars";
import { FieldError, FieldLabel, Input, Textarea } from "@/components/ui/Input";
import { Logo } from "@/components/ui/Logo";
import { Spinner } from "@/components/ui/Spinner";
import { UrgencyBadge } from "@/components/ui/UrgencyBadge";
import { useTheme } from "@/context/ThemeContext";
import { api, ApiError } from "@/lib/api";
import { REVIEW_THRESHOLD } from "@/lib/constants";
import type { PredictionPreview, TicketCreate, TicketDetail, TokenContribution } from "@/lib/types";
import { cn, formatPercent } from "@/lib/utils";

type Phase = "compose" | "analyzing" | "review" | "submitted";

interface Draft {
  subject: string;
  body: string;
  email: string;
}

const EMPTY_DRAFT: Draft = { subject: "", body: "", email: "" };

const EXAMPLES: { label: string; subject: string; body: string }[] = [
  {
    label: "Production outage",
    subject: "Checkout returns 500 for every customer",
    body: "Since about 20 minutes ago every checkout request fails with a 500 error. Our whole storefront is down and we are losing revenue every minute. Please escalate this immediately.",
  },
  {
    label: "Double charge",
    subject: "Charged twice on invoice INV-20415",
    body: "We were billed $1,204.50 twice this month for the same subscription. Finance needs a refund for the duplicate charge. Not an emergency, but we'd like it sorted this week.",
  },
  {
    label: "Locked out",
    subject: "Can't get past two-factor login",
    body: "My authenticator codes are rejected every time and I've been locked out of my account since this morning. Several people on my team rely on reports I can't open right now.",
  },
  {
    label: "Feature idea",
    subject: "Dark mode for the reports page",
    body: "It would be really nice to have a dark colour scheme for the reports page. Purely a nice-to-have, no rush at all.",
  },
];

const ANALYSIS_STEPS = [
  "Cleaning and normalising the text",
  "Scoring it against six categories",
  "Estimating how urgent it is",
];

// Inference takes a few milliseconds, which would make the result flash in
// before anyone registers what happened. The real latency is shown afterwards.
const MIN_ANALYSIS_MS = 1_400;

// Mirrors SLA_MINUTES in the backend taxonomy.
const RESPONSE_TARGETS = [
  { urgency: "Critical", target: "30 minutes" },
  { urgency: "High", target: "4 hours" },
  { urgency: "Medium", target: "1 business day" },
  { urgency: "Low", target: "3 business days" },
] as const;

const fade = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.25, ease: [0.22, 1, 0.36, 1] },
} as const;

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

function toPayload(draft: Draft): TicketCreate {
  return {
    subject: draft.subject.trim(),
    body: draft.body.trim(),
    requester_email: draft.email.trim() || null,
  };
}

function validate(payload: TicketCreate): Record<string, string> {
  const errors: Record<string, string> = {};
  if (payload.subject.length < 3) errors.subject = "Add a short subject (at least 3 characters).";
  if (payload.body.length < 10) errors.body = "Describe the problem in a little more detail.";
  if (payload.requester_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.requester_email)) {
    errors.requester_email = "That email address doesn't look right.";
  }
  return errors;
}

function mergeRationale(...lists: TokenContribution[][]): TokenContribution[] {
  const strongest = new Map<string, number>();
  for (const term of lists.flat()) {
    strongest.set(term.term, Math.max(strongest.get(term.term) ?? 0, term.weight));
  }
  return [...strongest]
    .map(([term, weight]) => ({ term, weight }))
    .sort((a, b) => b.weight - a.weight);
}

function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      onClick={toggleTheme}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
    >
      {theme === "dark" ? <Sun /> : <Moon />}
    </Button>
  );
}

function AnalyzingPanel() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const interval = window.setInterval(
      () => setStep((current) => Math.min(current + 1, ANALYSIS_STEPS.length)),
      MIN_ANALYSIS_MS / (ANALYSIS_STEPS.length + 0.5),
    );
    return () => window.clearInterval(interval);
  }, []);

  return (
    <div role="status" aria-live="polite" className="py-4">
      <div className="flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-xl bg-accent-soft text-accent">
          <Sparkles className="size-5 animate-pulse" />
        </span>
        <div>
          <p className="font-medium">Analyzing your ticket…</p>
          <p className="text-xs text-fg-muted">Reading it the way an agent would.</p>
        </div>
      </div>

      <div className="mt-6 h-1 overflow-hidden rounded-full bg-surface-3">
        <motion.div
          className="h-full rounded-full bg-linear-to-r from-accent to-cat-technical"
          initial={{ width: "0%" }}
          animate={{ width: "100%" }}
          transition={{ duration: MIN_ANALYSIS_MS / 1000, ease: "easeInOut" }}
        />
      </div>

      <ul className="mt-5 space-y-2.5">
        {ANALYSIS_STEPS.map((label, index) => {
          const done = index < step;
          const active = index === step;
          return (
            <li
              key={label}
              className={cn(
                "flex items-center gap-2.5 text-sm transition-colors",
                done ? "text-fg" : active ? "text-fg-muted" : "text-fg-subtle",
              )}
            >
              <span
                className={cn(
                  "grid size-5 place-items-center rounded-full border",
                  done ? "border-low/30 bg-low-soft text-low" : "border-line",
                )}
              >
                {done ? <Check className="size-3" /> : active ? <Spinner className="size-3 text-accent" /> : null}
              </span>
              {label}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function PredictionTile({
  label,
  confidence,
  uncertain,
  children,
}: {
  label: string;
  confidence: number;
  uncertain: boolean;
  children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-line bg-surface-2/50 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-subtle">{label}</p>
      <div className="mt-2.5">{children}</div>
      <div className="mt-3 flex items-baseline gap-1.5">
        <span
          className={cn(
            "font-mono text-2xl font-semibold tracking-tight tabular-nums",
            uncertain ? "text-medium" : "text-fg",
          )}
        >
          {formatPercent(confidence)}
        </span>
        <span className="text-xs text-fg-muted">confidence</span>
      </div>
    </div>
  );
}

export default function SubmitPage() {
  const [phase, setPhase] = useState<Phase>("compose");
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [prediction, setPrediction] = useState<PredictionPreview | null>(null);
  const [created, setCreated] = useState<TicketDetail | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const showError = (error: unknown) => {
    if (error instanceof ApiError) {
      setErrors(error.fieldErrors);
      setFormError(Object.keys(error.fieldErrors).length ? null : error.message);
    } else {
      setFormError("Something went wrong. Please try again.");
    }
  };

  const submit = useMutation({
    mutationFn: (payload: TicketCreate) => api.createTicket(payload),
    onSuccess: (ticket) => {
      setCreated(ticket);
      setPhase("submitted");
    },
    onError: (error) => {
      showError(error);
      setPhase("compose");
    },
  });

  const update = (field: keyof Draft) => (value: string) => {
    setDraft((current) => ({ ...current, [field]: value }));
    if (errors[field === "email" ? "requester_email" : field]) setErrors({});
  };

  const analyze = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const payload = toPayload(draft);
    const problems = validate(payload);
    setErrors(problems);
    setFormError(null);
    if (Object.keys(problems).length > 0) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setPhase("analyzing");

    try {
      const [result] = await Promise.all([
        api.classify(payload, controller.signal),
        sleep(MIN_ANALYSIS_MS),
      ]);
      if (controller.signal.aborted) return;
      setPrediction(result);
      setPhase("review");
    } catch (error) {
      if (controller.signal.aborted) return;
      showError(error);
      setPhase("compose");
    }
  };

  const reset = () => {
    setDraft(EMPTY_DRAFT);
    setPrediction(null);
    setCreated(null);
    setErrors({});
    setFormError(null);
    setPhase("compose");
  };

  const categoryUncertain = prediction ? prediction.category_confidence < REVIEW_THRESHOLD.category : false;
  const urgencyUncertain = prediction ? prediction.urgency_confidence < REVIEW_THRESHOLD.urgency : false;

  return (
    <div className="relative min-h-dvh overflow-hidden bg-canvas">
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute inset-x-0 top-0 h-[28rem] bg-grid opacity-40 [mask-image:linear-gradient(to_bottom,black,transparent)]" />
        <div className="absolute left-1/2 top-[-12rem] size-[40rem] -translate-x-1/2 rounded-full bg-accent/15 blur-[140px]" />
      </div>

      <header className="relative mx-auto flex h-16 max-w-5xl items-center justify-between px-5">
        <div className="flex items-center gap-3">
          <Logo />
          <span className="hidden h-4 w-px bg-line sm:block" />
          <span className="hidden text-sm text-fg-muted sm:block">Customer support</span>
        </div>
        <div className="flex items-center gap-1">
          <Link
            to="/"
            className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-sm text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg"
          >
            Agent dashboard
            <ArrowUpRight className="size-4" />
          </Link>
          <ThemeToggle />
        </div>
      </header>

      <main className="relative mx-auto grid max-w-5xl gap-8 px-5 pb-16 pt-6 lg:grid-cols-[1fr_20rem] lg:gap-12 lg:pt-12">
        <section className="min-w-0">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          >
            <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
              How can we help?
            </h1>
            <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-fg-muted">
              Describe the problem. Our triage model reads it instantly and routes it to the right
              team — and you'll see exactly how it was classified before you send it.
            </p>
          </motion.div>

          <div className="mt-8 rounded-2xl border border-line bg-surface p-5 shadow-panel sm:p-7">
            <AnimatePresence mode="wait" initial={false}>
              {phase === "compose" && (
                <motion.form key="compose" onSubmit={analyze} noValidate className="space-y-5" {...fade}>
                  <div>
                    <p className="mb-2 text-xs text-fg-subtle">Try an example</p>
                    <div className="flex flex-wrap gap-1.5">
                      {EXAMPLES.map((example) => (
                        <button
                          key={example.label}
                          type="button"
                          onClick={() => {
                            setDraft((current) => ({ ...current, subject: example.subject, body: example.body }));
                            setErrors({});
                          }}
                          className="inline-flex h-7 items-center gap-1.5 rounded-full border border-line bg-surface-2 px-2.5 text-xs text-fg-muted transition-colors hover:border-line-strong hover:text-fg"
                        >
                          <WandSparkles className="size-3" />
                          {example.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <FieldLabel htmlFor="requester-email">
                      Email <span className="font-normal text-fg-subtle">(optional)</span>
                    </FieldLabel>
                    <Input
                      id="requester-email"
                      type="email"
                      icon={Mail}
                      autoComplete="email"
                      placeholder="you@company.com"
                      value={draft.email}
                      onChange={(event) => update("email")(event.target.value)}
                      aria-invalid={errors.requester_email ? true : undefined}
                      aria-describedby="requester-email-error"
                    />
                    <FieldError id="requester-email-error">{errors.requester_email}</FieldError>
                  </div>

                  <div>
                    <FieldLabel htmlFor="subject">Subject</FieldLabel>
                    <Input
                      id="subject"
                      maxLength={200}
                      placeholder="A one-line summary of the problem"
                      value={draft.subject}
                      onChange={(event) => update("subject")(event.target.value)}
                      aria-invalid={errors.subject ? true : undefined}
                      aria-describedby="subject-error"
                    />
                    <FieldError id="subject-error">{errors.subject}</FieldError>
                  </div>

                  <div>
                    <div className="flex items-baseline justify-between">
                      <FieldLabel htmlFor="body">What's going on?</FieldLabel>
                      <span className="font-mono text-[11px] text-fg-subtle tabular-nums">
                        {draft.body.length}/5000
                      </span>
                    </div>
                    <Textarea
                      id="body"
                      rows={7}
                      maxLength={5000}
                      placeholder="What happened, who is affected, and how badly it is hurting you."
                      value={draft.body}
                      onChange={(event) => update("body")(event.target.value)}
                      aria-invalid={errors.body ? true : undefined}
                      aria-describedby="body-hint body-error"
                    />
                    <FieldError id="body-error">{errors.body}</FieldError>
                    {/* Tickets that state their impact are classified far more
                        accurately (see MODEL.md), so the form asks for it. */}
                    <p id="body-hint" className="mt-1.5 text-xs text-fg-subtle">
                      Tip: say who's affected and how badly — it's the biggest factor in routing your
                      ticket correctly.
                    </p>
                  </div>

                  {formError && (
                    <p
                      role="alert"
                      className="flex items-center gap-2 rounded-lg border border-critical/25 bg-critical-soft px-3 py-2 text-xs text-critical"
                    >
                      <CircleAlert className="size-3.5 shrink-0" />
                      {formError}
                    </p>
                  )}

                  <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                    <p className="text-xs text-fg-subtle">Nothing is sent until you confirm.</p>
                    <Button type="submit" variant="primary" size="lg">
                      <ScanSearch />
                      Analyze ticket
                    </Button>
                  </div>
                </motion.form>
              )}

              {phase === "analyzing" && (
                <motion.div key="analyzing" {...fade}>
                  <AnalyzingPanel />
                </motion.div>
              )}

              {phase === "review" && prediction && (
                <motion.div key="review" className="space-y-6" {...fade}>
                  <div>
                    <h2 className="text-lg font-semibold tracking-tight">Here's how we'd route it</h2>
                    <p className="mt-1 text-sm text-fg-muted">
                      Review the classification, then send it to the queue.
                    </p>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <PredictionTile label="Category" confidence={prediction.category_confidence} uncertain={categoryUncertain}>
                      <CategoryTag category={prediction.category} uncertain={categoryUncertain} />
                    </PredictionTile>
                    <PredictionTile label="Urgency" confidence={prediction.urgency_confidence} uncertain={urgencyUncertain}>
                      <UrgencyBadge urgency={prediction.urgency} size="md" uncertain={urgencyUncertain} />
                    </PredictionTile>
                  </div>

                  {(categoryUncertain || urgencyUncertain) && (
                    <p className="flex items-start gap-2 rounded-lg border border-medium/25 bg-medium-soft px-3 py-2.5 text-xs leading-relaxed">
                      <TriangleAlert className="mt-px size-3.5 shrink-0 text-medium" />
                      The model isn't confident about the{" "}
                      {categoryUncertain && urgencyUncertain ? "category or the urgency" : categoryUncertain ? "category" : "urgency"}
                      , so an agent will double-check it rather than route it blindly.
                    </p>
                  )}

                  <div className="grid gap-6 sm:grid-cols-2">
                    <div>
                      <p className="mb-2.5 text-[11px] font-medium text-fg-subtle">Urgency breakdown</p>
                      <ConfidenceBars
                        scores={prediction.urgency_scores}
                        toneFor={urgencyBarTone}
                        highlight={prediction.urgency}
                        threshold={REVIEW_THRESHOLD.urgency}
                      />
                    </div>
                    <div>
                      <p className="mb-2.5 text-[11px] font-medium text-fg-subtle">Category breakdown</p>
                      <ConfidenceBars
                        scores={prediction.category_scores}
                        toneFor={categoryBarTone}
                        highlight={prediction.category}
                        threshold={REVIEW_THRESHOLD.category}
                      />
                    </div>
                  </div>

                  <div>
                    <p className="mb-2 text-[11px] font-medium text-fg-subtle">Phrases that shaped this</p>
                    <Rationale
                      terms={mergeRationale(prediction.urgency_rationale, prediction.category_rationale)}
                      limit={8}
                    />
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
                    <p className="font-mono text-[11px] text-fg-subtle">
                      classified in {prediction.inference_ms.toFixed(1)}ms
                    </p>
                    <div className="flex gap-2">
                      <Button variant="ghost" onClick={() => setPhase("compose")} disabled={submit.isPending}>
                        <PenLine />
                        Edit
                      </Button>
                      <Button
                        variant="primary"
                        loading={submit.isPending}
                        onClick={() => submit.mutate(toPayload(draft))}
                      >
                        {!submit.isPending && <Send />}
                        Submit to queue
                      </Button>
                    </div>
                  </div>
                </motion.div>
              )}

              {phase === "submitted" && created && (
                <motion.div key="submitted" className="py-6 text-center" {...fade}>
                  <motion.span
                    initial={{ scale: 0.6, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ type: "spring", stiffness: 380, damping: 22, delay: 0.05 }}
                    className="mx-auto grid size-14 place-items-center rounded-full bg-low-soft text-low"
                  >
                    <CircleCheckBig className="size-7" />
                  </motion.span>
                  <h2 className="mt-5 text-xl font-semibold tracking-tight">Ticket received</h2>
                  <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-fg-muted">
                    Your reference is{" "}
                    <span className="font-mono font-medium text-fg">{created.reference}</span>. It's
                    in the queue as {created.category.toLowerCase()} with{" "}
                    {created.urgency.toLowerCase()} urgency.
                  </p>
                  <div className="mt-6 flex flex-wrap justify-center gap-2">
                    <Button onClick={reset}>Submit another</Button>
                    <Link
                      to={`/?ticket=${created.id}`}
                      className="inline-flex h-9 items-center gap-2 rounded-lg bg-accent px-3.5 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-hover"
                    >
                      View in dashboard
                      <ArrowUpRight className="size-4" />
                    </Link>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </section>

        <aside className="space-y-4 lg:pt-28">
          <div className="rounded-2xl border border-line bg-surface/70 p-5 backdrop-blur">
            <h2 className="text-sm font-semibold">How triage works</h2>
            <ol className="mt-4 space-y-4">
              {[
                ["Read", "Your message is cleaned and scored by a lightweight model trained on 1,400 support tickets."],
                ["Route", "It's tagged with a category and an urgency, then placed in the matching queue."],
                ["Review", "If the model isn't confident, an agent checks it before anything else happens."],
              ].map(([title, text], index) => (
                <li key={title} className="flex gap-3">
                  <span className="grid size-6 shrink-0 place-items-center rounded-full border border-line bg-surface-2 font-mono text-[11px] text-fg-muted">
                    {index + 1}
                  </span>
                  <div>
                    <p className="text-sm font-medium">{title}</p>
                    <p className="text-xs leading-relaxed text-fg-muted">{text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          <div className="rounded-2xl border border-line bg-surface/70 p-5 backdrop-blur">
            <h2 className="text-sm font-semibold">First-response targets</h2>
            <dl className="mt-3 divide-y divide-line">
              {RESPONSE_TARGETS.map(({ urgency, target }) => (
                <div key={urgency} className="flex items-center justify-between py-2 text-xs">
                  <dt>
                    <UrgencyBadge urgency={urgency} />
                  </dt>
                  <dd className="font-mono text-fg-muted">{target}</dd>
                </div>
              ))}
            </dl>
          </div>
        </aside>
      </main>
    </div>
  );
}
