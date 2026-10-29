import { useState, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  confirmLabel: string;
  onConfirm: () => void | Promise<void>;
  className?: string;
  disabled?: boolean;
}

/** A destructive action asks twice: the first click arms the button, the second one does it. */
export function ConfirmButton({
  children,
  confirmLabel,
  onConfirm,
  className = "btn btn-danger-quiet",
  disabled,
}: Props) {
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!armed) {
    return (
      <button
        className={className}
        disabled={disabled}
        onClick={() => setArmed(true)}
      >
        {children}
      </button>
    );
  }
  return (
    <span className="confirm">
      <button
        className="btn btn-danger"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await onConfirm();
          } finally {
            setBusy(false);
            setArmed(false);
          }
        }}
      >
        {busy ? "Working…" : confirmLabel}
      </button>
      <button
        className="btn btn-quiet"
        disabled={busy}
        onClick={() => setArmed(false)}
      >
        Keep
      </button>
    </span>
  );
}
