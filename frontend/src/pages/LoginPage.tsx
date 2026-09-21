import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  ArrowRight,
  CircleAlert,
  Eye,
  EyeOff,
  Lock,
  Mail,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { FieldLabel, Input } from "@/components/ui/Input";
import { Logo } from "@/components/ui/Logo";
import { useAuth } from "@/context/AuthContext";
import { api, ApiError } from "@/lib/api";
import { DEMO_CREDENTIALS } from "@/lib/constants";
import { queryKeys } from "@/lib/query";
import type { Health } from "@/lib/types";
import { cn } from "@/lib/utils";

const EASE = [0.22, 1, 0.36, 1] as const;

const FEATURES = [
  {
    icon: Zap,
    title: "Classified in milliseconds",
    text: "Every ticket gets a category and urgency the moment it lands.",
  },
  {
    icon: ShieldCheck,
    title: "Knows when it's unsure",
    text: "Low-confidence calls are flagged for a human instead of routed blindly.",
  },
  {
    icon: Sparkles,
    title: "Explains itself",
    text: "See the phrases behind every prediction, and override in one click.",
  },
];

function Backdrop() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-grid opacity-50 [mask-image:radial-gradient(ellipse_at_30%_40%,black,transparent_70%)]" />
      <div className="absolute -left-40 -top-40 size-[36rem] animate-drift rounded-full bg-accent/25 blur-[120px]" />
      <div className="absolute -bottom-48 left-1/4 size-[32rem] animate-drift rounded-full bg-cat-technical/15 blur-[120px] [animation-delay:-7s]" />
      <div className="absolute -right-32 top-1/4 size-[28rem] animate-drift rounded-full bg-cat-bug/10 blur-[120px] [animation-delay:-14s]" />
    </div>
  );
}

function ApiStatus({ health }: { health: UseQueryResult<Health> }) {
  const state = health.isPending
    ? { dot: "bg-medium", text: "Checking the API…" }
    : health.isError
      ? { dot: "bg-critical", text: "API unreachable — is the backend running on port 8000?" }
      : health.data.model_loaded
        ? { dot: "bg-low", text: `API online · model loaded · ${health.data.ticket_count} tickets` }
        : { dot: "bg-medium", text: "API online · model artifacts missing" };

  return (
    <p className="mt-4 flex items-center justify-center gap-2 text-[11px] text-fg-subtle">
      <span className={cn("size-1.5 rounded-full", state.dot)} />
      {state.text}
    </p>
  );
}

export default function LoginPage() {
  const { status, login } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const health = useQuery({
    queryKey: queryKeys.health,
    queryFn: api.health,
    retry: false,
    refetchInterval: (query) => (query.state.status === "error" ? 5_000 : false),
  });

  if (status === "authenticated") return <Navigate to={from} replace />;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? (caught.fieldErrors.email ?? caught.message)
          : "Something went wrong. Please try again.",
      );
      setSubmitting(false);
    }
  };

  const useDemoAccount = () => {
    setEmail(DEMO_CREDENTIALS.email);
    setPassword(DEMO_CREDENTIALS.password);
    setError(null);
  };

  return (
    <div className="relative grid min-h-dvh overflow-hidden bg-canvas lg:grid-cols-[1.1fr_1fr]">
      <Backdrop />

      <aside className="relative hidden flex-col justify-between p-10 lg:flex xl:p-14">
        <Logo />

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: EASE }}
          className="max-w-md"
        >
          <p className="inline-flex items-center gap-2 rounded-full border border-line bg-surface/60 px-3 py-1 text-xs text-fg-muted backdrop-blur">
            <span className="size-1.5 rounded-full bg-low" />
            Agent workspace
          </p>
          <h1 className="mt-5 text-4xl font-semibold leading-[1.1] tracking-tight text-balance">
            Every ticket, triaged before you've read it.
          </h1>
          <p className="mt-4 text-[15px] leading-relaxed text-fg-muted">
            TriageAI classifies incoming support tickets by topic and urgency, routes them to the
            right queue, and shows you exactly why.
          </p>

          <ul className="mt-8 space-y-4">
            {FEATURES.map(({ icon: Icon, title, text }, index) => (
              <motion.li
                key={title}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.15 + index * 0.08, duration: 0.5, ease: EASE }}
                className="flex gap-3"
              >
                <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-line bg-surface/70 text-accent backdrop-blur">
                  <Icon className="size-4" />
                </span>
                <div>
                  <p className="text-sm font-medium">{title}</p>
                  <p className="text-sm text-fg-muted">{text}</p>
                </div>
              </motion.li>
            ))}
          </ul>
        </motion.div>

        <p className="font-mono text-[11px] text-fg-subtle">
          TF-IDF + logistic regression · ~4ms per ticket · no external AI APIs
        </p>
      </aside>

      <main className="relative flex items-center justify-center p-5 sm:p-10">
        <motion.div
          initial={{ opacity: 0, y: 16, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.5, ease: EASE }}
          className="w-full max-w-sm"
        >
          <div className="mb-8 lg:hidden">
            <Logo />
          </div>

          <div className="rounded-2xl border border-line bg-surface/80 p-6 shadow-overlay backdrop-blur-xl sm:p-8">
            <h2 className="text-xl font-semibold tracking-tight">Sign in</h2>
            <p className="mt-1 text-sm text-fg-muted">Work the queue as a support agent.</p>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
              <div>
                <FieldLabel htmlFor="email">Email</FieldLabel>
                <Input
                  id="email"
                  type="email"
                  autoComplete="username"
                  icon={Mail}
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="you@company.com"
                  aria-invalid={error ? true : undefined}
                  required
                  autoFocus
                />
              </div>

              <div>
                <FieldLabel htmlFor="password">Password</FieldLabel>
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  icon={Lock}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  aria-invalid={error ? true : undefined}
                  required
                  trailing={
                    <button
                      type="button"
                      onClick={() => setShowPassword((value) => !value)}
                      aria-label={showPassword ? "Hide password" : "Show password"}
                      className="grid size-7 place-items-center rounded-md text-fg-subtle transition-colors hover:text-fg"
                    >
                      {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  }
                />
              </div>

              {error && (
                <p
                  role="alert"
                  className="flex items-center gap-2 rounded-lg border border-critical/25 bg-critical-soft px-3 py-2 text-xs text-critical"
                >
                  <CircleAlert className="size-3.5 shrink-0" />
                  {error}
                </p>
              )}

              <Button
                type="submit"
                variant="primary"
                size="lg"
                loading={submitting}
                disabled={!email || !password}
                className="w-full"
              >
                Sign in
                {!submitting && <ArrowRight />}
              </Button>
            </form>

            <div className="mt-5 flex items-center justify-between gap-3 rounded-xl border border-dashed border-line-strong bg-surface-2/50 p-3">
              <div className="min-w-0">
                <p className="text-xs font-medium">Demo account</p>
                <p className="truncate font-mono text-[11px] text-fg-subtle">
                  {DEMO_CREDENTIALS.email} · {DEMO_CREDENTIALS.password}
                </p>
              </div>
              <Button size="sm" onClick={useDemoAccount}>
                Use it
              </Button>
            </div>
          </div>

          <ApiStatus health={health} />

          <p className="mt-6 text-center text-xs text-fg-muted">
            Here as a customer?{" "}
            <Link to="/submit" className="font-medium text-fg underline-offset-4 hover:underline">
              Submit a ticket
            </Link>
          </p>
        </motion.div>
      </main>
    </div>
  );
}
