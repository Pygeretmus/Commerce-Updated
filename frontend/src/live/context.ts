import { createContext, useContext } from "react";
import type { AppNotification, Summary } from "../api/types";

export interface Toast {
  id: number;
  notification: AppNotification;
}

export interface LiveState {
  summary: Summary | null;
  refreshSummary: () => void;
  toasts: Toast[];
  dismissToast: (id: number) => void;
  /** Goes up whenever a notification arrives: pages that show personal lists reload on it. */
  pulse: number;
}

export const LiveContext = createContext<LiveState | null>(null);

export function useLive(): LiveState {
  const value = useContext(LiveContext);
  if (!value) throw new Error("useLive must be used inside <LiveProvider>");
  return value;
}
