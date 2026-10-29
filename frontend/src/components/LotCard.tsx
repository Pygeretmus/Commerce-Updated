import { Link } from "react-router-dom";
import type { ListingListItem } from "../api/types";
import { formatMoney, lotNumber, plural } from "../format";
import { Countdown } from "./Countdown";

export function LotCard({ lot }: { lot: ListingListItem }) {
  const closed = lot.status !== "active" || lot.is_ended;
  const priceLabel = closed
    ? lot.sold
      ? "Sold for"
      : "Closing price"
    : lot.bids_count === 0
      ? "Starting bid"
      : "Current bid";

  return (
    <article className="lot-card">
      <Link to={`/lots/${lot.id}`} className="lot-card-link">
        <div className="lot-card-photo">
          {lot.cover ? (
            <img src={lot.cover} alt="" loading="lazy" />
          ) : (
            <div className="photo-missing">No photo</div>
          )}
          <span className="lot-number">{lotNumber(lot.id)}</span>
          {closed && (
            <span className={`lot-ribbon${lot.sold ? " lot-ribbon-sold" : ""}`}>
              {lot.sold
                ? "Sold"
                : lot.status === "cancelled"
                  ? "Withdrawn"
                  : "Closed"}
            </span>
          )}
        </div>
        <div className="lot-card-body">
          <p className="eyebrow">{lot.category.name}</p>
          <h3 className="lot-card-title">{lot.title}</h3>
          <div className="lot-card-foot">
            <div>
              <p className="label">{priceLabel}</p>
              <p className="price">{formatMoney(lot.current_price)}</p>
              <p className="muted small">{plural(lot.bids_count, "bid")}</p>
            </div>
            <div className="lot-card-time">
              <p className="label">{closed ? "Ended" : "Ends in"}</p>
              <Countdown endsAt={lot.ends_at} ended={closed} />
            </div>
          </div>
        </div>
      </Link>
    </article>
  );
}
