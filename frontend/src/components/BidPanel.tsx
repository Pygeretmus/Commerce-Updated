import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { biddingApi } from "../api/endpoints";
import type { ListingDetail, PlacedBid } from "../api/types";
import { useAuth } from "../auth/context";
import { formatDate, formatMoney, plural } from "../format";
import { Countdown } from "./Countdown";
import { FormErrors } from "./Field";

interface Props {
  lot: ListingDetail;
  skew: number;
  onPlaced: (placed: PlacedBid) => void;
}

function ReserveLine({ lot }: { lot: ListingDetail }) {
  if (!lot.has_reserve) return <p className="muted small">No reserve price.</p>;
  if (lot.is_seller && lot.reserve_price)
    return (
      <p className="muted small">
        Your reserve: {formatMoney(lot.reserve_price)} (
        {lot.reserve_met ? "met" : "not met yet"}).
      </p>
    );
  return (
    <p className="muted small">
      {lot.reserve_met ? "Reserve price met." : "Reserve price not met yet."}
    </p>
  );
}

function Result({ lot }: { lot: ListingDetail }) {
  if (lot.status === "cancelled") {
    return (
      <div className="notice">
        <p className="notice-title">Withdrawn by the seller</p>
        <p className="muted small">This lot did not go to auction.</p>
      </div>
    );
  }
  if (lot.sold) {
    return (
      <div className="notice notice-good">
        <p className="notice-title">
          Sold for {formatMoney(lot.current_price)}
        </p>
        <p className="muted small">
          Winning bidder: {lot.winner ?? "a deleted account"}.
        </p>
      </div>
    );
  }
  return (
    <div className="notice">
      <p className="notice-title">
        {lot.bids_count === 0
          ? "Closed without bids"
          : "Closed: reserve not met"}
      </p>
      <p className="muted small">
        {lot.bids_count === 0
          ? "Nobody bid on this lot."
          : `The highest bid, ${formatMoney(lot.current_price)}, stayed below the reserve.`}
      </p>
    </div>
  );
}

function OwnerControls({ lot }: { lot: ListingDetail }) {
  const [error] = useState<ApiError | null>(null);
  if (lot.status !== "active") return null;

  return (
    <div className="owner-controls">
      <p className="label">You are the seller</p>
      <FormErrors messages={error?.errors.map((e) => e.message) ?? []} />
      <p className="muted small">
        {lot.bids_count > 0
          ? "A lot with bids cannot be withdrawn."
          : "Once somebody bids, the lot can no longer be withdrawn."}
      </p>
    </div>
  );
}

export function BidPanel({ lot, skew, onPlaced }: Props) {
  const { user } = useAuth();
  const [typed, setTyped] = useState<string | undefined>(undefined);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [placed, setPlaced] = useState<string | null>(null);

  const open = lot.status === "active" && !lot.is_ended;
  const amount = typed ?? lot.next_min_bid;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setPlaced(null);
    try {
      const result = await biddingApi.place(lot.id, amount.trim());
      setTyped(undefined);
      setPlaced(result.bid.amount);
      onPlaced(result);
    } catch (e) {
      const apiError = e instanceof ApiError ? e : null;
      setError(apiError);
      // Somebody was faster, or the auction closed: show the new numbers
      if (
        apiError?.errors.some((x) =>
          ["bid_too_low", "auction_closed", "already_top_bidder"].includes(
            x.code,
          ),
        )
      ) {
        setTyped(undefined);
      }
    } finally {
      setBusy(false);
    }
  };

  const priceLabel = !open
    ? lot.sold
      ? "Sold for"
      : "Closing price"
    : lot.bids_count === 0
      ? "Starting bid"
      : "Current bid";

  return (
    <aside className="paddle" aria-label="Bidding">
      <p className="label">{priceLabel}</p>
      <p className="price price-large" aria-live="polite" aria-atomic="true">
        {formatMoney(lot.current_price)}
        <span className="visually-hidden">
          {lot.leader ? `, held by ${lot.leader}` : ", no bids yet"}
        </span>
      </p>
      <p className="muted small">
        {plural(lot.bids_count, "bid")}
        {lot.leader && open && <> · highest bidder {lot.leader}</>}
      </p>
      <ReserveLine lot={lot} />

      <div className="paddle-time">
        <div>
          <p className="label">{open ? "Closes in" : "Closed"}</p>
          <Countdown endsAt={lot.ends_at} skew={skew} ended={!open} large />
        </div>
        <p className="muted small">
          {open
            ? `on ${formatDate(lot.ends_at)}`
            : formatDate(lot.closed_at ?? lot.ends_at)}
        </p>
      </div>
      {open && (
        <p className="muted small">
          A bid in the last two minutes extends the auction by two minutes.
        </p>
      )}

      {open && lot.my_bid_status === "winning" && (
        <div className="notice notice-good" role="status">
          <p className="notice-title">You are the highest bidder</p>
        </div>
      )}
      {open && lot.my_bid_status === "outbid" && (
        <div className="notice notice-warn" role="status">
          <p className="notice-title">You have been outbid</p>
          <p className="small">
            The minimum bid is now {formatMoney(lot.next_min_bid)}.
          </p>
        </div>
      )}

      {!open && (
        <>
          <Result lot={lot} />
          {lot.my_bid_status === "won" && (
            <div className="notice notice-good">
              <p className="notice-title">You won this lot</p>
            </div>
          )}
          {lot.my_bid_status === "lost" && (
            <div className="notice">
              <p className="notice-title">You did not win this lot</p>
            </div>
          )}
        </>
      )}

      {open && lot.is_seller && <OwnerControls lot={lot} />}

      {open && !lot.is_seller && user && lot.my_bid_status !== "winning" && (
        <form className="bid-form" onSubmit={submit} noValidate>
          <FormErrors messages={error?.errors.map((e) => e.message) ?? []} />
          <label htmlFor="bid-amount">Your bid</label>
          <div className="money-input">
            <span aria-hidden="true">$</span>
            <input
              id="bid-amount"
              inputMode="decimal"
              autoComplete="off"
              value={amount}
              onChange={(e) => setTyped(e.target.value)}
              aria-describedby="bid-hint"
              required
            />
          </div>
          <p id="bid-hint" className="hint">
            Minimum bid:{" "}
            <span className="mono">{formatMoney(lot.next_min_bid)}</span>
          </p>
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy
              ? "Placing bid…"
              : `Place bid · ${formatMoney(amount || "0")}`}
          </button>
        </form>
      )}
      {open &&
        !lot.is_seller &&
        user &&
        lot.my_bid_status === "winning" &&
        placed && (
          <p className="muted small" role="status">
            Your bid of {formatMoney(placed)} was accepted.
          </p>
        )}
      {open && !user && user !== undefined && (
        <Link
          className="btn btn-primary btn-block"
          to={`/login?next=${encodeURIComponent(`/lots/${lot.id}`)}`}
        >
          Sign in to bid
        </Link>
      )}
    </aside>
  );
}
