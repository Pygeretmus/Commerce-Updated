import { Link } from "react-router-dom";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

export default function NotFound() {
  useDocumentTitle("Not found");
  return (
    <div className="narrow centered">
      <p className="eyebrow">Error 404</p>
      <h1>This lot is not in the catalogue.</h1>
      <p className="muted">
        The page may have been withdrawn, or the address is mistyped.
      </p>
      <Link className="btn" to="/">
        Back to the catalogue
      </Link>
    </div>
  );
}
