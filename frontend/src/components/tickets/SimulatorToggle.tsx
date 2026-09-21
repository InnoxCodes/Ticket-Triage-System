import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Zap } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { api, ApiError } from "@/lib/api";
import { queryKeys } from "@/lib/query";
import type { SimulatorState } from "@/lib/types";

export function SimulatorToggle() {
  const queryClient = useQueryClient();
  const state = useQuery({ queryKey: queryKeys.simulator, queryFn: api.simulator });

  const toggle = useMutation({
    mutationFn: (run: boolean) => (run ? api.startSimulator() : api.stopSimulator()),
    onSuccess: (next) => {
      queryClient.setQueryData<SimulatorState>(queryKeys.simulator, next);
      toast(next.running ? "Simulating live traffic" : "Traffic simulation paused", {
        description: next.running
          ? `A fresh, model-unseen ticket arrives roughly every ${Math.round(next.interval_seconds)}s.`
          : undefined,
      });
    },
    onError: (error) =>
      toast.error("Couldn't toggle the simulator", {
        description: error instanceof ApiError ? error.message : undefined,
      }),
  });

  const running = state.data?.running ?? false;

  return (
    <Button
      variant={running ? "secondary" : "outline"}
      loading={toggle.isPending}
      disabled={state.isLoading}
      onClick={() => toggle.mutate(!running)}
      aria-pressed={running}
      title="Inject realistic tickets on a timer to watch the live feed"
    >
      {!toggle.isPending &&
        (running ? (
          <span className="relative flex size-2">
            <span className="absolute inset-0 animate-pulse-ring rounded-full bg-low" />
            <span className="relative size-2 rounded-full bg-low" />
          </span>
        ) : (
          <Zap />
        ))}
      {running ? "Simulating" : "Simulate traffic"}
      {running && <Pause className="text-fg-subtle" />}
    </Button>
  );
}
