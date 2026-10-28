import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";

interface Result<T> {
  key: string;
  data?: T;
  error?: ApiError;
  receivedAt: number;
}

export interface Fetched<T> {
  data: T | undefined;
  error: ApiError | undefined;
  /** True until the answer for the current key arrives. With `keepPrevious` the old data stays visible meanwhile. */
  loading: boolean;
  /** Browser time (ms) when `data` arrived: pairs with a server timestamp to measure the clock skew. */
  receivedAt: number;
  reload: () => void;
  /** Replace the data locally (after an action whose result is already known). */
  mutate: (updater: (current: T) => T) => void;
}

const NETWORK_ERROR = () =>
  new ApiError(0, [
    {
      param: null,
      message: "Network error. Check your connection.",
      code: "network",
    },
  ]);

/**
 * Loads data when `key` changes (and again on reload()). `load` gets an AbortSignal, so a slow answer to an old
 * request can never overwrite the answer to a newer one.
 */
export function useFetch<T>(
  key: string,
  load: (signal: AbortSignal) => Promise<T>,
  options: { keepPrevious?: boolean } = {},
): Fetched<T> {
  const [result, setResult] = useState<Result<T>>({ key: "", receivedAt: 0 });
  const [tick, setTick] = useState(0);

  // The latest `load` (it is a new function on every render) without making the effect depend on it
  const loader = useRef(load);
  useEffect(() => {
    loader.current = load;
  });

  useEffect(() => {
    const controller = new AbortController();
    loader
      .current(controller.signal)
      .then((data) => setResult({ key, data, receivedAt: Date.now() }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const apiError = error instanceof ApiError ? error : NETWORK_ERROR();
        setResult((previous) => ({
          key,
          data: previous.key === key ? previous.data : undefined,
          error: apiError,
          receivedAt: previous.receivedAt,
        }));
      });
    return () => controller.abort();
  }, [key, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  const mutate = useCallback(
    (updater: (current: T) => T) =>
      setResult((previous) =>
        previous.data === undefined
          ? previous
          : { ...previous, data: updater(previous.data) },
      ),
    [],
  );

  const fresh = result.key === key;
  const visible = fresh || options.keepPrevious ? result : undefined;
  return {
    data: visible?.data,
    error: fresh ? result.error : undefined,
    loading: !fresh,
    receivedAt: visible?.receivedAt ?? 0,
    reload,
    mutate,
  };
}
