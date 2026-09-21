import { Spinner } from "@/components/ui/Spinner";

export function PageLoader() {
  return (
    <div className="grid min-h-dvh place-items-center bg-canvas" role="status" aria-live="polite">
      <div className="flex items-center gap-3 text-sm text-fg-subtle">
        <Spinner className="text-accent" />
        Loading TriageAI…
      </div>
    </div>
  );
}
