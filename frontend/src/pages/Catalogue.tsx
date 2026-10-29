import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { catalogApi, type ListingQuery } from "../api/endpoints";
import { LotCard } from "../components/LotCard";
import { Pagination } from "../components/Pagination";
import { Empty, ErrorNote, Loading } from "../components/StateNote";
import { useDebounced } from "../hooks/useDebounced";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useFirstPageOn404 } from "../hooks/useFirstPageOn404";
import { useFetch } from "../hooks/useFetch";
import { plural } from "../format";

const ORDERINGS = [
  { value: "newest", label: "Newest first" },
  { value: "ending_soon", label: "Ending soonest" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "most_bids", label: "Most bids" },
];

export default function Catalogue() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") === "ended" ? "ended" : "active";
  const ordering =
    params.get("ordering") ?? (status === "ended" ? "newest" : "ending_soon");
  const category = params.get("category") ?? "";
  const q = params.get("q") ?? "";
  const minPrice = params.get("min_price") ?? "";
  const maxPrice = params.get("max_price") ?? "";
  const page = Number(params.get("page") ?? 1) || 1;

  useDocumentTitle(status === "ended" ? "Closed sales" : "Catalogue");

  const categories = useFetch("categories", () => catalogApi.categories());

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page"); // a new filter starts from the first page
    setParams(next, { replace: true });
  };

  // The search box types freely and updates the address a moment after you stop
  const [typed, setTyped] = useState<string | null>(null);
  const debounced = useDebounced(typed);
  useEffect(() => {
    if (debounced !== null && debounced !== q) {
      const next = new URLSearchParams(params);
      if (debounced) next.set("q", debounced);
      else next.delete("q");
      next.delete("page");
      setParams(next, { replace: true });
    }
    // only when the debounced text changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  const query: ListingQuery = {
    status,
    ordering,
    q: q || undefined,
    category: category || undefined,
    min_price: minPrice || undefined,
    max_price: maxPrice || undefined,
    page,
  };
  const lots = useFetch(
    `lots:${params.toString()}`,
    (signal) => catalogApi.list(query, signal),
    { keepPrevious: true },
  );

  useFirstPageOn404(lots.error, page, () => update({ page: null }));

  const hasFilters = Boolean(q || category || minPrice || maxPrice);

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">
          {status === "ended" ? "The archive" : "On the block now"}
        </p>
        <h1>{status === "ended" ? "Closed sales" : "The current catalogue"}</h1>
        {lots.data && (
          <p className="muted">
            {plural(lots.data.count, "lot")}{" "}
            {status === "ended" ? "sold or closed" : "open for bidding"}
            {hasFilters && " matching your filters"}
          </p>
        )}
      </header>

      <form
        className="filters"
        role="search"
        onSubmit={(event) => event.preventDefault()}
      >
        <div className="field filter-search">
          <label htmlFor="q">Search</label>
          <input
            id="q"
            type="search"
            placeholder="A vase, a watch, a map…"
            value={typed ?? q}
            onChange={(event) => setTyped(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="category">Category</label>
          <select
            id="category"
            value={category}
            onChange={(event) => update({ category: event.target.value })}
          >
            <option value="">All categories</option>
            {categories.data?.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="ordering">Sort by</label>
          <select
            id="ordering"
            value={ordering}
            onChange={(event) => update({ ordering: event.target.value })}
          >
            {ORDERINGS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field filter-price">
          <label htmlFor="min_price">Price</label>
          <div className="range">
            <input
              key={`min-${minPrice}`}
              id="min_price"
              inputMode="decimal"
              placeholder="Min"
              aria-label="Minimum price"
              defaultValue={minPrice}
              onBlur={(event) =>
                update({ min_price: event.target.value.trim() || null })
              }
              onKeyDown={(event) =>
                event.key === "Enter" && event.currentTarget.blur()
              }
            />
            <span aria-hidden="true">–</span>
            <input
              key={`max-${maxPrice}`}
              inputMode="decimal"
              placeholder="Max"
              aria-label="Maximum price"
              defaultValue={maxPrice}
              onBlur={(event) =>
                update({ max_price: event.target.value.trim() || null })
              }
              onKeyDown={(event) =>
                event.key === "Enter" && event.currentTarget.blur()
              }
            />
          </div>
        </div>
        {hasFilters && (
          <button
            type="button"
            className="btn btn-quiet"
            onClick={() => {
              setTyped("");
              setParams(status === "ended" ? { status } : {}, {
                replace: true,
              });
            }}
          >
            Clear filters
          </button>
        )}
      </form>

      {lots.error && <ErrorNote error={lots.error} onRetry={lots.reload} />}
      {!lots.data && !lots.error && <Loading label="Opening the catalogue…" />}
      {lots.data && lots.data.results.length === 0 && (
        <Empty title="Nothing matches.">
          {hasFilters
            ? "Try fewer words or a wider price range."
            : "No lots here yet."}
        </Empty>
      )}
      {lots.data && lots.data.results.length > 0 && (
        <div className={`lot-grid${lots.loading ? " is-loading" : ""}`}>
          {lots.data.results.map((lot) => (
            <LotCard key={lot.id} lot={lot} />
          ))}
        </div>
      )}
      {lots.data && (
        <Pagination
          page={page}
          count={lots.data.count}
          onChange={(next) => update({ page: String(next) })}
        />
      )}
    </>
  );
}
