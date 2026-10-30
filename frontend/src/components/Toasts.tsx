import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useLive } from "../live/context";

const LIFETIME_MS = 9000;

function ToastItem({
  id,
  text,
  listingId,
}: {
  id: number;
  text: string;
  listingId: number;
}) {
  const { dismissToast } = useLive();
  useEffect(() => {
    const timer = setTimeout(() => dismissToast(id), LIFETIME_MS);
    return () => clearTimeout(timer);
  }, [id, dismissToast]);

  return (
    <div className="toast">
      <p>{text}</p>
      <div className="toast-actions">
        <Link to={`/lots/${listingId}`} onClick={() => dismissToast(id)}>
          View lot →
        </Link>
        <button
          className="btn btn-quiet"
          onClick={() => dismissToast(id)}
          aria-label="Dismiss"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

export function Toasts() {
  const { toasts } = useLive();
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map(({ id, notification }) => (
        <ToastItem
          key={id}
          id={id}
          text={notification.text}
          listingId={notification.listing.id}
        />
      ))}
    </div>
  );
}
