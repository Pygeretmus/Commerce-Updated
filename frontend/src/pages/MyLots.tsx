import { Link, useSearchParams } from "react-router-dom";
import { Tabs } from "../components/Tabs";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

export default function MyLots() {
  useDocumentTitle("My lots");
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";

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
        tabs={[]}
      />
    </>
  );
}
