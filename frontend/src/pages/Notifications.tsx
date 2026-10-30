import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { meApi } from "../api/endpoints";
import type { NotificationKind } from "../api/types";
import { Pagination } from "../components/Pagination";
import { Empty, ErrorNote, Loading } from "../components/StateNote";
import { timeAgo } from "../format";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useFirstPageOn404 } from "../hooks/useFirstPageOn404";
import { useFetch } from "../hooks/useFetch";
import { useLive } from "../live/context";

const GLYPH: Record<NotificationKind, string> = {
  outbid: "↯",
  won: "★",
  sold: "$",
  lost: "○",
  ending_soon: "◷",
  new_comment: "✎",
  listing_ended: "■",
  cancelled: "✕",
};

export default function Notifications() {
  useDocumentTitle("Notifications");
  const navigate = useNavigate();
  const { summary, refreshSummary, pulse } = useLive();
  const [page, setPage] = useState(1);
  const [error, setError] = useState<ApiError | null>(null);
  const list = useFetch(
    `notifications:${page}:${pulse}`,
    (signal) => meApi.notifications(page, signal),
    { keepPrevious: true },
  );
  useFirstPageOn404(list.error, page, () => setPage(1));
  const unread = summary?.unread_notifications ?? 0;

  const markAll = async () => {
    try {
      await meApi.markRead({ all: true });
      refreshSummary();
      list.reload();
    } catch (e) {
      setError(e instanceof ApiError ? e : null);
    }
  };

  const open = async (id: number, listingId: number, wasUnread: boolean) => {
    if (wasUnread) {
      try {
        await meApi.markRead({ ids: [id] });
        refreshSummary();
      } catch {
        /* opening the lot matters more than the read mark */
      }
    }
    navigate(`/lots/${listingId}`);
  };

  return (
    <>
      <header className="page-head page-head-row">
        <div>
          <p className="eyebrow">The post room</p>
          <h1>Notifications</h1>
        </div>
        <button className="btn" onClick={markAll} disabled={unread === 0}>
          Mark all as read
        </button>
      </header>
      {error && <ErrorNote error={error} />}
      {list.error && <ErrorNote error={list.error} onRetry={list.reload} />}
      {!list.data && !list.error && <Loading />}
      {list.data?.results.length === 0 && (
        <Empty title="Nothing yet.">
          You will hear about outbids, wins and lots that are about to end.{" "}
          <Link to="/">Browse the catalogue</Link>
        </Empty>
      )}
      {list.data && list.data.results.length > 0 && (
        <ul className="notifications">
          {list.data.results.map((n) => (
            <li
              key={n.id}
              className={n.read_at ? "notification" : "notification is-unread"}
            >
              <span className={`glyph glyph-${n.kind}`} aria-hidden="true">
                {GLYPH[n.kind]}
              </span>
              <button
                className="notification-text"
                onClick={() => open(n.id, n.listing.id, !n.read_at)}
              >
                {n.text}
                {!n.read_at && (
                  <span className="visually-hidden"> (unread)</span>
                )}
              </button>
              <time className="muted small" dateTime={n.created_at}>
                {timeAgo(n.created_at)}
              </time>
            </li>
          ))}
        </ul>
      )}
      {list.data && (
        <Pagination page={page} count={list.data.count} onChange={setPage} />
      )}
    </>
  );
}
