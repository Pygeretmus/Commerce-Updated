import { useEffect, useRef } from "react";

interface Options<E> {
  /** Returns the address to open, or null to stay disconnected. May be async (tickets). */
  getUrl: () => Promise<string | null> | string | null;
  onEvent: (event: E) => void;
  /** Called after a REconnect: events may have been missed, so the caller should reload its data. */
  onReconnect?: () => void;
  enabled?: boolean;
  /** Close codes after which the server will never agree (for example 4404: no such lot): stop retrying. */
  stopOn?: number[];
}

const MAX_DELAY = 30_000;
// A connection that closes sooner than this did not really work (the server may accept and then close at once),
// so the retry delay keeps growing instead of starting over.
const STABLE_AFTER = 10_000;
const NO_RETRY_CODES = [4404];

/**
 * A WebSocket that reconnects with exponential backoff (1 s, 2 s, 4 s ... 30 s, plus jitter).
 * The page must keep working when the socket never connects, so nothing here ever throws or blocks.
 */
export function useSocket<E>(
  {
    getUrl,
    onEvent,
    onReconnect,
    enabled = true,
    stopOn = NO_RETRY_CODES,
  }: Options<E>,
  deps: unknown[],
): void {
  const handlers = useRef({ getUrl, onEvent, onReconnect });
  useEffect(() => {
    handlers.current = { getUrl, onEvent, onReconnect };
  });

  useEffect(() => {
    if (!enabled) return;
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stableTimer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    let everConnected = false;
    let stopped = false;

    const schedule = () => {
      if (stopped) return;
      const delay =
        Math.min(1000 * 2 ** attempts, MAX_DELAY) * (0.8 + Math.random() * 0.4);
      attempts += 1;
      timer = setTimeout(connect, delay);
    };

    const connect = async () => {
      if (stopped) return;
      let url: string | null;
      try {
        url = await handlers.current.getUrl();
      } catch {
        schedule();
        return;
      }
      if (stopped || !url) return;
      socket = new WebSocket(url);
      socket.onopen = () => {
        stableTimer = setTimeout(() => (attempts = 0), STABLE_AFTER);
        if (everConnected) handlers.current.onReconnect?.();
        everConnected = true;
      };
      socket.onmessage = (message) => {
        try {
          handlers.current.onEvent(JSON.parse(message.data as string) as E);
        } catch {
          /* ignore malformed frames */
        }
      };
      socket.onclose = (event) => {
        socket = null;
        clearTimeout(stableTimer);
        if (!stopOn.includes(event.code)) schedule();
      };
      socket.onerror = () => socket?.close();
    };

    void connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      clearTimeout(stableTimer);
      if (socket) {
        socket.onclose = null;
        socket.close();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps]);
}
