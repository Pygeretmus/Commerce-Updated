import { Link, useSearchParams } from "react-router-dom";
import { meApi } from "../api/endpoints";
import type { MyListingItem } from "../api/types";
import { Countdown } from "../components/Countdown";
import { Pagination } from "../components/Pagination";
import { Empty, ErrorNote, Loading } from "../components/StateNote";
import { Tabs } from "../components/Tabs";
import { formatDate, formatMoney, lotNumber, plural } from "../format";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useFirstPageOn404 } from "../hooks/useFirstPageOn404";
import { useFetch } from "../hooks/useFetch";
import { useLive } from "../live/context";

const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  active: "Live",
  ended: "Closed",
  cancelled: "Withdrawn",
};

function Row({ lot }: { lot: MyListingItem }) {
  const live = lot.status === "active" && !lot.is_ended;
  return (
    <li className="row">
      <Link
        to={lot.status === "draft" ? `/lots/${lot.id}/edit` : `/lots/${lot.id}`}
        className="row-photo"
      >
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
          <Link
            to={
              lot.status === "draft"
                ? `/lots/${lot.id}/edit`
                : `/lots/${lot.id}`
            }
          >
            {lot.title}
          </Link>
        </h3>
        <p className="muted small">
          {lot.status === "draft" && `Created ${formatDate(lot.created_at)}`}
          {live && (
            <>
              Closes in <Countdown endsAt={lot.ends_at} />
            </>
          )}
          {lot.status === "ended" &&
            (lot.sold
              ? `Sold to ${lot.winner ?? "a deleted account"}`
              : "Closed without a sale")}
          {lot.status === "cancelled" && "Withdrawn by you"}
        </p>
      </div>
      <div className="row-figures">
        <span className={`status status-${live ? "active" : lot.status}`}>
          {live ? "Live" : STATUS_LABEL[lot.status]}
        </span>
        <p className="price">{formatMoney(lot.current_price)}</p>
        <p className="muted small">
          {lot.status === "draft"
            ? "not published"
            : plural(lot.bids_count, "bid")}
        </p>
        {lot.reserve_price && (
          <p className="muted small">
            reserve {formatMoney(lot.reserve_price)}
          </p>
        )}
      </div>
    </li>
  );
}

export default function MyLots() {
  useDocumentTitle("My lots");
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const page = Number(params.get("page") ?? 1) || 1;
  const { summary, pulse } = useLive();
  const lots = useFetch(
    `mylots:${status}:${page}:${pulse}`,
    (signal) => meApi.listings(status || undefined, page, signal),
    { keepPrevious: true },
  );

  const counts = summary?.listings;
  const total = counts
    ? Object.values(counts).reduce((a, b) => a + b, 0)
    : undefined;

  useFirstPageOn404(lots.error, page, () =>
    setParams(status ? { status } : {}),
  );

  return (
    <>
      <header className="page-head page-head-row">
        <div>
          <p className="eyebrow">Consignments</p>
          <h1>My lots</h1>
        </div>
        <Link className="btn btn-primary" to="/sell">
          Sell a lot
        </Link>
      </header>
      <Tabs
        label="Filter by status"
        active={status}
        onChange={(value) => setParams(value ? { status: value } : {})}
        tabs={[
          { value: "", label: "All", count: total },
          { value: "draft", label: "Drafts", count: counts?.draft },
          { value: "active", label: "Live", count: counts?.active },
          { value: "ended", label: "Closed", count: counts?.ended },
          { value: "cancelled", label: "Withdrawn", count: counts?.cancelled },
        ]}
      />
      {lots.error && <ErrorNote error={lots.error} onRetry={lots.reload} />}
      {!lots.data && !lots.error && <Loading />}
      {lots.data?.results.length === 0 && (
        <Empty title="Nothing here.">
          <Link to="/sell">Consign your first lot</Link>
        </Empty>
      )}
      {lots.data && lots.data.results.length > 0 && (
        <ul className="rows">
          {lots.data.results.map((lot) => (
            <Row key={lot.id} lot={lot} />
          ))}
        </ul>
      )}
      {lots.data && (
        <Pagination
          page={page}
          count={lots.data.count}
          onChange={(next) =>
            setParams({ ...(status ? { status } : {}), page: String(next) })
          }
        />
      )}
    </>
  );
}
