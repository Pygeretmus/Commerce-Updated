import { Link, useSearchParams } from "react-router-dom";
import { meApi } from "../api/endpoints";
import type { BidStatus, MyBidItem } from "../api/types";
import { Countdown } from "../components/Countdown";
import { Pagination } from "../components/Pagination";
import { Empty, ErrorNote, Loading } from "../components/StateNote";
import { Tabs } from "../components/Tabs";
import { formatMoney, lotNumber } from "../format";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useFirstPageOn404 } from "../hooks/useFirstPageOn404";
import { useFetch } from "../hooks/useFetch";
import { useLive } from "../live/context";

const LABEL: Record<BidStatus, string> = {
  winning: "Winning",
  outbid: "Outbid",
  won: "Won",
  lost: "Lost",
};

function Row({ lot }: { lot: MyBidItem }) {
  return (
    <li className="row">
      <Link to={`/lots/${lot.id}`} className="row-photo">
        {lot.cover ? (
          <img src={lot.cover} alt="" loading="lazy" />
        ) : (
          <span className="photo-missing small">No photo</span>
        )}
      </Link>
      <div className="row-main">
        <p className="eyebrow mono">
          {lotNumber(lot.id)} · {lot.category.name}
        </p>
        <h3>
          <Link to={`/lots/${lot.id}`}>{lot.title}</Link>
        </h3>
        <p className="muted small">
          {lot.status === "active" ? (
            <>
              Closes in <Countdown endsAt={lot.ends_at} ended={lot.is_ended} />
            </>
          ) : (
            "Closed"
          )}
        </p>
      </div>
      <div className="row-figures">
        <span className={`status status-${lot.my_status}`}>
          {LABEL[lot.my_status]}
        </span>
        <p className="price">{formatMoney(lot.current_price)}</p>
        <p className="muted small">
          your highest: {formatMoney(lot.my_highest_bid)}
        </p>
      </div>
    </li>
  );
}

export default function MyBids() {
  useDocumentTitle("My bids");
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const page = Number(params.get("page") ?? 1) || 1;
  const { summary, pulse } = useLive();
  const bids = useFetch(
    `mybids:${status}:${page}:${pulse}`,
    (signal) => meApi.bids(status || undefined, page, signal),
    { keepPrevious: true },
  );
  const counts = summary?.bids;
  const total = counts
    ? counts.winning + counts.outbid + counts.won + counts.lost
    : undefined;

  useFirstPageOn404(bids.error, page, () =>
    setParams(status ? { status } : {}),
  );

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">Your paddle</p>
        <h1>My bids</h1>
      </header>
      <Tabs
        label="Filter by result"
        active={status}
        onChange={(value) => setParams(value ? { status: value } : {})}
        tabs={[
          { value: "", label: "All", count: total },
          { value: "winning", label: "Winning", count: counts?.winning },
          { value: "outbid", label: "Outbid", count: counts?.outbid },
          { value: "won", label: "Won", count: counts?.won },
          { value: "lost", label: "Lost", count: counts?.lost },
        ]}
      />
      {bids.error && <ErrorNote error={bids.error} onRetry={bids.reload} />}
      {!bids.data && !bids.error && <Loading />}
      {bids.data?.results.length === 0 && (
        <Empty title="No bids here.">
          <Link to="/">Browse the catalogue</Link> and place your first bid.
        </Empty>
      )}
      {bids.data && bids.data.results.length > 0 && (
        <ul className="rows">
          {bids.data.results.map((lot) => (
            <Row key={lot.id} lot={lot} />
          ))}
        </ul>
      )}
      {bids.data && (
        <Pagination
          page={page}
          count={bids.data.count}
          onChange={(next) =>
            setParams({ ...(status ? { status } : {}), page: String(next) })
          }
        />
      )}
    </>
  );
}
