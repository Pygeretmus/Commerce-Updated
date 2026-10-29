import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { wsUrl } from "../api/client";
import { catalogApi, discussionApi } from "../api/endpoints";
import type { ListingEvent, PlacedBid } from "../api/types";
import { useAuth } from "../auth/context";
import { BidPanel } from "../components/BidPanel";
import { Gallery } from "../components/Gallery";
import { ErrorNote, Loading } from "../components/StateNote";
import { lotNumber } from "../format";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useFetch } from "../hooks/useFetch";
import { useSocket } from "../hooks/useSocket";
import NotFound from "./NotFound";

interface Clock {
  serverTime: string;
  at: number;
}

export default function Lot() {
  const { id } = useParams();
  const { user } = useAuth();
  const listingId = Number(id);
  const lot = useFetch(`lot:${id}:${user?.id ?? "anon"}`, (signal) =>
    catalogApi.get(listingId, signal),
  );
  const data = lot.data;
  const [clock, setClock] = useState<Clock | null>(null);
  const [watchError, setWatchError] = useState<ApiError | null>(null);

  useDocumentTitle(data?.title);

  // Live updates. The page works without them: the socket only makes it faster.
  const { mutate, reload } = lot;
  useSocket<ListingEvent>(
    {
      // a draft has no public channel (the server refuses it), so wait until we know what the lot is
      enabled:
        Number.isFinite(listingId) &&
        !lot.error &&
        data !== undefined &&
        data.status !== "draft",
      getUrl: () => wsUrl(`/ws/listings/${listingId}/`),
      onEvent: (event) => {
        if (event.type === "price_update") {
          setClock({ serverTime: event.server_time, at: Date.now() });
          mutate((d) => ({
            ...d,
            current_price: event.current_price,
            bids_count: event.bids_count,
            next_min_bid: event.next_min_bid,
            ends_at: event.ends_at,
            leader: event.leader,
          }));
          // "Am I still winning?" depends on who the masked name is: ask the server, but only people who
          // have bid (everybody else already has all they need in the event; this saves a request per viewer)
          if (data?.my_bid_status != null) reload();
        } else if (event.type === "listing_ended") {
          setClock({ serverTime: event.server_time, at: Date.now() });
          reload();
        }
      },
      onReconnect: reload,
    },
    [listingId],
  );

  // The newest clock reading wins: the page load or the last live event
  const reading: Clock | null = data
    ? clock && clock.at > lot.receivedAt
      ? clock
      : { serverTime: data.server_time, at: lot.receivedAt }
    : null;
  const skew = reading
    ? new Date(reading.serverTime).getTime() - reading.at
    : 0;

  // When the clock reaches zero the page must not wait for a push that may never come (socket down, closer late):
  // it asks the server every few seconds until the lot is closed.
  useEffect(() => {
    if (!data || data.status !== "active" || !data.ends_at) return;
    const endsAt = new Date(data.ends_at).getTime();
    const timer = setInterval(() => {
      if (Date.now() + skew >= endsAt) reload();
    }, 5000);
    return () => clearInterval(timer);
  }, [data, skew, reload]);

  if (lot.error?.status === 404 || !Number.isFinite(listingId))
    return <NotFound />;
  if (lot.error && !data)
    return <ErrorNote error={lot.error} onRetry={lot.reload} />;
  if (!data) return <Loading label="Fetching the lot…" />;

  const onPlaced = (placed: PlacedBid) => {
    setClock({ serverTime: placed.state.server_time, at: Date.now() });
    mutate((d) => ({ ...d, ...placed.state, my_bid_status: "winning" }));
    lot.reload();
  };

  const toggleWatch = async () => {
    setWatchError(null);
    try {
      if (data.is_watching) await discussionApi.unwatch(data.id);
      else await discussionApi.watch(data.id);
      mutate((d) => ({ ...d, is_watching: !d.is_watching }));
    } catch (e) {
      setWatchError(e instanceof ApiError ? e : null);
    }
  };

  const editable = data.is_seller && data.status === "draft";

  return (
    <>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link to="/">Catalogue</Link> <span aria-hidden="true">/</span>{" "}
        <Link to={`/?category=${data.category.slug}`}>
          {data.category.name}
        </Link>{" "}
        <span aria-hidden="true">/</span>{" "}
        <span className="mono">{lotNumber(data.id)}</span>
      </nav>

      <div className="lot-layout">
        <div className="lot-main">
          <Gallery images={data.images} title={data.title} />
          <section className="section" aria-labelledby="desc-title">
            <h2 id="desc-title">About this lot</h2>
            <p className="prose">{data.description}</p>
          </section>
        </div>

        <div className="lot-side">
          <p className="eyebrow">
            <span className="mono">{lotNumber(data.id)}</span> ·{" "}
            {data.category.name}
          </p>
          <h1 className="lot-title">{data.title}</h1>
          <p className="muted">
            Consigned by <strong>{data.seller ?? "a deleted account"}</strong>
          </p>

          {data.status === "draft" ? (
            <div className="notice">
              <p className="notice-title">This is a draft</p>
              <p className="small">
                Only you can see it. Add photographs and publish it to start the
                auction.
              </p>
              {editable && (
                <Link className="btn btn-primary" to={`/lots/${data.id}/edit`}>
                  Continue editing
                </Link>
              )}
            </div>
          ) : (
            <>
              <BidPanel lot={data} skew={skew} onPlaced={onPlaced} />
              {user && !data.is_seller && (
                <div className="watch">
                  <button
                    className="btn btn-quiet"
                    onClick={toggleWatch}
                    aria-pressed={data.is_watching}
                  >
                    {data.is_watching ? "★ Watching" : "☆ Watch this lot"}
                  </button>
                  {watchError && (
                    <p className="field-error">{watchError.message}</p>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
