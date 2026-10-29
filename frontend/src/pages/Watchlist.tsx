import { useSearchParams } from "react-router-dom";
import { catalogApi } from "../api/endpoints";
import { LotCard } from "../components/LotCard";
import { Pagination } from "../components/Pagination";
import { Empty, ErrorNote, Loading } from "../components/StateNote";
import { Tabs } from "../components/Tabs";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useFetch } from "../hooks/useFetch";
import { useFirstPageOn404 } from "../hooks/useFirstPageOn404";

export default function Watchlist() {
  useDocumentTitle("Watchlist");
  const [params, setParams] = useSearchParams();
  const status = params.get("status") === "ended" ? "ended" : "active";
  const page = Number(params.get("page") ?? 1) || 1;
  // Open lots by the time they close; closed ones, the latest first (the order of "ending soon" would put
  // the oldest finished lots on top)
  const lots = useFetch(
    `watching:${status}:${page}`,
    (signal) =>
      catalogApi.list(
        {
          watching: true,
          status,
          ordering: status === "active" ? "ending_soon" : "newest",
          page,
        },
        signal,
      ),
    { keepPrevious: true },
  );
  useFirstPageOn404(lots.error, page, () => setParams({ status }));

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">Your shortlist</p>
        <h1>Watchlist</h1>
      </header>
      <Tabs
        label="Open or closed lots"
        active={status}
        onChange={(value) => setParams({ status: value })}
        tabs={[
          { value: "active", label: "Open" },
          { value: "ended", label: "Closed" },
        ]}
      />
      {lots.error && <ErrorNote error={lots.error} onRetry={lots.reload} />}
      {!lots.data && !lots.error && <Loading />}
      {lots.data?.results.length === 0 && (
        <Empty
          title={
            status === "active"
              ? "You are not watching any open lots."
              : "None of your watched lots has closed."
          }
        >
          Press “Watch” on a lot page to keep it here and be told when it is
          about to end.
        </Empty>
      )}
      {lots.data && lots.data.results.length > 0 && (
        <div className="lot-grid">
          {lots.data.results.map((lot) => (
            <LotCard key={lot.id} lot={lot} />
          ))}
        </div>
      )}
      {lots.data && (
        <Pagination
          page={page}
          count={lots.data.count}
          onChange={(next) => setParams({ status, page: String(next) })}
        />
      )}
    </>
  );
}
