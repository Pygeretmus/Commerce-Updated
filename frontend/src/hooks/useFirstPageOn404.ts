import { useEffect } from "react";
import type { ApiError } from "../api/client";

/** A list that no longer has this page (items were removed, filters changed) falls back to the first one. */
export function useFirstPageOn404(
  error: ApiError | undefined,
  page: number,
  goToFirst: () => void,
): void {
  useEffect(() => {
    if (error?.status === 404 && page > 1) goToFirst();
    // goToFirst is a new function on every render; only a new error should trigger it
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [error, page]);
}
