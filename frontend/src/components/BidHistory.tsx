import { useState } from "react";
import { biddingApi } from "../api/endpoints";
import { formatMoney, plural, timeAgo } from "../format";
import { useFetch } from "../hooks/useFetch";
import { Pagination } from "./Pagination";
import { ErrorNote } from "./StateNote";

/** The history reloads by itself whenever `bidsCount` changes (a live update or my own bid). */
export function BidHistory({
  listingId,
  bidsCount,
}: {
  listingId: number;
  bidsCount: number;
}) {
  const [page, setPage] = useState(1);
  const history = useFetch(
    `bids:${listingId}:${bidsCount}:${page}`,
    (signal) => biddingApi.history(listingId, page, signal),
    {
      keepPrevious: true,
    },
  );

  return (
    <section className="section" aria-labelledby="history-title">
      <h2 id="history-title">Bidding history</h2>
      {history.error && (
        <ErrorNote error={history.error} onRetry={history.reload} />
      )}
      {history.data && history.data.count === 0 && (
        <p className="muted">No bids yet. The first bid sets the price.</p>
      )}
      {history.data && history.data.count > 0 && (
        <>
          <p className="muted small">
            {plural(history.data.count, "bid")}; bidders appear with their first
            and last letters only.
          </p>
          <table className="ledger">
            <thead>
              <tr>
                <th scope="col">Bidder</th>
                <th scope="col" className="num">
                  Amount
                </th>
                <th scope="col" className="num">
                  When
                </th>
              </tr>
            </thead>
            <tbody>
              {history.data.results.map((bid, index) => (
                <tr
                  key={bid.id}
                  className={bid.is_mine ? "is-mine" : undefined}
                >
                  <td>
                    {bid.bidder ?? <em>Deleted user</em>}
                    {bid.is_mine && <span className="tag">you</span>}
                    {page === 1 && index === 0 && (
                      <span className="tag tag-lead">highest</span>
                    )}
                  </td>
                  <td className="num mono">{formatMoney(bid.amount)}</td>
                  <td className="num muted">{timeAgo(bid.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination
            page={page}
            count={history.data.count}
            onChange={setPage}
          />
        </>
      )}
    </section>
  );
}
