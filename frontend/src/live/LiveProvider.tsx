import { useCallback, useMemo, useState, type ReactNode } from "react";
import { wsUrl } from "../api/client";
import { meApi } from "../api/endpoints";
import type { UserEvent } from "../api/types";
import { useAuth } from "../auth/context";
import { useFetch } from "../hooks/useFetch";
import { useSocket } from "../hooks/useSocket";
import { LiveContext, type Toast } from "./context";

/**
 * Everything personal and live for a signed-in user: the counters in the navigation (loaded from the API)
 * and the notification socket. If the socket never connects the counters still refresh when pages ask for it.
 */
export function LiveProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const userId = user?.id ?? null;

  const summary = useFetch<import("../api/types").Summary | null>(
    `summary:${userId}`,
    (signal) =>
      userId === null ? Promise.resolve(null) : meApi.summary(signal),
  );
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [pulse, setPulse] = useState(0);
  const { reload } = summary;

  const dismissToast = useCallback(
    (id: number) =>
      setToasts((list) => list.filter((toast) => toast.id !== id)),
    [],
  );

  useSocket<UserEvent>(
    {
      enabled: userId !== null,
      getUrl: async () => {
        const { ticket } = await meApi.wsTicket();
        return wsUrl(`/ws/me/?ticket=${encodeURIComponent(ticket)}`);
      },
      onEvent: (event) => {
        if (event.type !== "notification") return;
        setToasts((list) =>
          [...list, { id: event.id, notification: event }].slice(-4),
        );
        setPulse((value) => value + 1);
        reload();
      },
      onReconnect: reload,
    },
    [userId],
  );

  const value = useMemo(
    () => ({
      summary: summary.data ?? null,
      refreshSummary: reload,
      toasts,
      dismissToast,
      pulse,
    }),
    [summary.data, reload, toasts, dismissToast, pulse],
  );
  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}
