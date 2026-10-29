import { formatRemaining, useCountdown } from "../hooks/useCountdown";

interface Props {
  endsAt: string | null;
  skew?: number;
  /** The server says bidding is over (status or end time): show that instead of a clock. */
  ended?: boolean;
  large?: boolean;
}

export function Countdown({
  endsAt,
  skew = 0,
  ended = false,
  large = false,
}: Props) {
  const remaining = useCountdown(endsAt, skew);
  const className = `countdown${large ? " countdown-large" : ""}`;

  if (ended || remaining === null)
    return <span className={className}>Closed</span>;
  if (remaining === 0)
    return <span className={`${className} countdown-closing`}>Closing…</span>;

  const urgent = remaining < 5 * 60 * 1000;
  return (
    <time
      className={`${className}${urgent ? " countdown-urgent" : ""}`}
      dateTime={endsAt ?? undefined}
    >
      {formatRemaining(remaining)}
      <span className="visually-hidden"> remaining</span>
    </time>
  );
}
