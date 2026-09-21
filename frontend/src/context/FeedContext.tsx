import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { toast } from "sonner";

import { useAuth } from "@/context/AuthContext";
import { websocketUrl } from "@/lib/api";
import { queryKeys } from "@/lib/query";
import type { FeedEvent, TicketPage, TicketSummary } from "@/lib/types";

export type FeedStatus = "connecting" | "live" | "offline";

// While the socket is down the board falls back to polling at this interval,
// so it is never stale for longer than this even without a live connection.
export const FALLBACK_POLL_MS = 8_000;

const FRESH_HIGHLIGHT_MS = 6_000;
const MAX_BACKOFF_MS = 30_000;
const UNAUTHORIZED_CLOSE_CODE = 4401;

interface FeedContextValue {
  status: FeedStatus;
  isFresh: (ticketId: number) => boolean;
}

const FeedContext = createContext<FeedContextValue | null>(null);

function upsertTicket(
  page: TicketPage | undefined,
  ticket: TicketSummary,
  insertIfMissing: boolean,
): TicketPage | undefined {
  if (!page) return page;

  const index = page.items.findIndex((item) => item.id === ticket.id);
  if (index >= 0) {
    const items = page.items.slice();
    items[index] = ticket;
    return { ...page, items };
  }

  if (!insertIfMissing) return page;
  return {
    ...page,
    items: [ticket, ...page.items].slice(0, page.page_size),
    total: page.total + 1,
  };
}

export function FeedProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { token } = useAuth();

  const [status, setStatus] = useState<FeedStatus>("connecting");
  const [freshIds, setFreshIds] = useState<ReadonlySet<number>>(() => new Set());
  const freshTimers = useRef(new Map<number, number>());

  const markFresh = useCallback((ticketId: number) => {
    setFreshIds((previous) => new Set(previous).add(ticketId));

    const existing = freshTimers.current.get(ticketId);
    if (existing) window.clearTimeout(existing);

    freshTimers.current.set(
      ticketId,
      window.setTimeout(() => {
        freshTimers.current.delete(ticketId);
        setFreshIds((previous) => {
          const next = new Set(previous);
          next.delete(ticketId);
          return next;
        });
      }, FRESH_HIGHLIGHT_MS),
    );
  }, []);

  const handleEvent = useCallback(
    (event: FeedEvent) => {
      switch (event.type) {
        case "ticket.created":
          queryClient.setQueryData<TicketPage>(queryKeys.board, (page) =>
            upsertTicket(page, event.data, true),
          );
          markFresh(event.data.id);
          if (event.data.urgency === "Critical") {
            toast.error(`Critical ticket · ${event.data.reference}`, {
              description: event.data.subject,
            });
          }
          void queryClient.invalidateQueries({ queryKey: queryKeys.analyticsAll });
          break;

        case "ticket.updated":
        case "ticket.overridden":
          queryClient.setQueryData<TicketPage>(queryKeys.board, (page) =>
            upsertTicket(page, event.data, false),
          );
          void queryClient.invalidateQueries({ queryKey: queryKeys.ticket(event.data.id) });
          void queryClient.invalidateQueries({ queryKey: queryKeys.analyticsAll });
          break;

        case "stats.invalidated":
          void queryClient.invalidateQueries({ queryKey: queryKeys.tickets });
          void queryClient.invalidateQueries({ queryKey: queryKeys.analyticsAll });
          break;

        default:
          break;
      }
    },
    [markFresh, queryClient],
  );

  // Held in a ref so a new handler identity never tears down a healthy socket.
  const handleEventRef = useRef(handleEvent);
  useEffect(() => {
    handleEventRef.current = handleEvent;
  }, [handleEvent]);

  useEffect(() => {
    if (!token) {
      setStatus("offline");
      return;
    }

    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let attempt = 0;
    let connectedBefore = false;
    let disposed = false;

    const connect = () => {
      setStatus("connecting");
      const current = new WebSocket(websocketUrl("/ws/tickets"));
      socket = current;

      current.onopen = () => current.send(JSON.stringify({ type: "auth", token }));

      current.onmessage = (message) => {
        let event: FeedEvent;
        try {
          event = JSON.parse(String(message.data)) as FeedEvent;
        } catch {
          return;
        }

        if (event.type === "ready") {
          attempt = 0;
          setStatus("live");
          // Events that fired while disconnected were never delivered; resync.
          if (connectedBefore) {
            void queryClient.invalidateQueries({ queryKey: queryKeys.tickets });
            void queryClient.invalidateQueries({ queryKey: queryKeys.analyticsAll });
          }
          connectedBefore = true;
          return;
        }

        handleEventRef.current(event);
      };

      current.onclose = (closeEvent) => {
        if (socket === current) socket = null;
        if (disposed) return;

        setStatus("offline");
        // A rejected token will not start working on retry; the next REST call's
        // 401 ends the session instead.
        if (closeEvent.code === UNAUTHORIZED_CLOSE_CODE) return;

        const backoff = Math.min(MAX_BACKOFF_MS, 1_000 * 2 ** attempt);
        attempt += 1;
        retryTimer = window.setTimeout(connect, backoff * (0.7 + Math.random() * 0.6));
      };
    };

    connect();

    return () => {
      disposed = true;
      window.clearTimeout(retryTimer);
      socket?.close();
    };
  }, [queryClient, token]);

  useEffect(() => {
    const timers = freshTimers.current;
    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
      timers.clear();
    };
  }, []);

  const isFresh = useCallback((ticketId: number) => freshIds.has(ticketId), [freshIds]);
  const value = useMemo(() => ({ status, isFresh }), [status, isFresh]);

  return <FeedContext value={value}>{children}</FeedContext>;
}

export function useFeed(): FeedContextValue {
  const context = useContext(FeedContext);
  if (!context) throw new Error("useFeed must be used inside FeedProvider");
  return context;
}
