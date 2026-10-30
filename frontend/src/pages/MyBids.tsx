import { useSearchParams } from "react-router-dom";
import { Tabs } from "../components/Tabs";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

export default function MyBids() {
  useDocumentTitle("My bids");
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";

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
        tabs={[]}
      />
    </>
  );
}
