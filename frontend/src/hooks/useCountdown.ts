import { useEffect, useState } from "react";

/**
 * Milliseconds until `endsAt`, ticking every second. `skew` is (server time - browser time) measured when the
 * data was loaded, so a wrong clock on the visitor's computer does not make the countdown lie.
 */
export function useCountdown(
  endsAt: string | null,
  skew: number,
): number | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!endsAt) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [endsAt]);
  if (!endsAt) return null;
  return Math.max(0, new Date(endsAt).getTime() - (now + skew));
}

export function formatRemaining(ms: number): string {
  const total = Math.floor(ms / 1000);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}
