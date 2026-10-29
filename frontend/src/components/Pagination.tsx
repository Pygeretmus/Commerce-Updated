interface Props {
  page: number;
  count: number;
  pageSize?: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, count, pageSize = 20, onChange }: Props) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  if (pages <= 1) return null;
  return (
    <nav className="pagination" aria-label="Pages">
      <button
        className="btn btn-quiet"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        ← Previous
      </button>
      <span className="mono small">
        Page {page} of {pages}
      </span>
      <button
        className="btn btn-quiet"
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
      >
        Next →
      </button>
    </nav>
  );
}
