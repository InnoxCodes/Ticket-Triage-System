import { QueryClient } from "@tanstack/react-query";

import { ApiError, type TicketQuery } from "./api";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      // A 4xx will fail identically on retry; only network errors and 5xx are worth another attempt.
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.status >= 400 && error.status < 500) &&
        failureCount < 2,
    },
  },
});

// The board loads the newest tickets once and filters client-side, which keeps
// search and filter chips instant and gives the live feed one cache entry to patch.
export const BOARD_QUERY: TicketQuery = { page_size: 200, sort: "newest" };

export const queryKeys = {
  tickets: ["tickets"] as const,
  board: ["tickets", "board"] as const,
  ticket: (id: number) => ["ticket", id] as const,
  analyticsAll: ["analytics"] as const,
  analytics: (days: number) => ["analytics", days] as const,
  model: ["model-performance"] as const,
  simulator: ["simulator"] as const,
  health: ["health"] as const,
};
