import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { queryKeys } from "@/lib/query";
import type { TicketPage, TicketSummary, TicketUpdate } from "@/lib/types";

interface UpdateVariables {
  ticket: TicketSummary;
  patch: TicketUpdate;
}

function applyPatch(ticket: TicketSummary, patch: TicketUpdate): TicketSummary {
  const category = patch.category ?? ticket.category;
  const urgency = patch.urgency ?? ticket.urgency;

  let resolvedAt = ticket.resolved_at;
  if (patch.status === "Resolved") resolvedAt = new Date().toISOString();
  else if (patch.status) resolvedAt = null;

  return {
    ...ticket,
    ...patch,
    category,
    urgency,
    resolved_at: resolvedAt,
    was_overridden: category !== ticket.ai_category || urgency !== ticket.ai_urgency,
  };
}

function describe(ticket: TicketSummary, patch: TicketUpdate): { title: string; description?: string } {
  if (patch.urgency) {
    return {
      title: "Override logged",
      description: `${ticket.reference}: urgency ${ticket.urgency} → ${patch.urgency}`,
    };
  }
  if (patch.category) {
    return {
      title: "Override logged",
      description: `${ticket.reference}: category ${ticket.category} → ${patch.category}`,
    };
  }
  return { title: `${ticket.reference} moved to ${patch.status}` };
}

export function useUpdateTicket() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ticket, patch }: UpdateVariables) => api.updateTicket(ticket.id, patch),

    // Optimistic: a dropped card lands immediately instead of after a round
    // trip, and snaps back if the server rejects the change.
    onMutate: async ({ ticket, patch }: UpdateVariables) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.board });
      const previous = queryClient.getQueryData<TicketPage>(queryKeys.board);

      queryClient.setQueryData<TicketPage>(queryKeys.board, (page) =>
        page && {
          ...page,
          items: page.items.map((item) => (item.id === ticket.id ? applyPatch(item, patch) : item)),
        },
      );

      return { previous };
    },

    onError: (error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(queryKeys.board, context.previous);
      toast.error("Couldn't update the ticket", {
        description: error instanceof ApiError ? error.message : "Please try again.",
      });
    },

    onSuccess: (detail, { ticket, patch }) => {
      queryClient.setQueryData(queryKeys.ticket(detail.id), detail);
      queryClient.setQueryData<TicketPage>(queryKeys.board, (page) =>
        page && {
          ...page,
          items: page.items.map((item) => (item.id === detail.id ? detail : item)),
        },
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.analyticsAll });

      const { title, description } = describe(ticket, patch);
      toast.success(title, { description });
    },
  });
}
