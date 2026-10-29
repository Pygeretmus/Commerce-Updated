import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { discussionApi } from "../api/endpoints";
import { useAuth } from "../auth/context";
import { timeAgo } from "../format";
import { useFetch } from "../hooks/useFetch";
import { FormErrors } from "./Field";
import { Pagination } from "./Pagination";
import { ErrorNote } from "./StateNote";

export function Comments({
  listingId,
  isSeller,
}: {
  listingId: number;
  isSeller: boolean;
}) {
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const comments = useFetch(
    `comments:${listingId}:${page}`,
    (signal) => discussionApi.comments(listingId, page, signal),
    {
      keepPrevious: true,
    },
  );
  const [body, setBody] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await discussionApi.post(listingId, body);
      setBody("");
      // The new comment is at the end: go to the last page
      const last = Math.max(
        1,
        Math.ceil(((comments.data?.count ?? 0) + 1) / 20),
      );
      if (last === page) comments.reload();
      else setPage(last);
    } catch (e) {
      setError(e instanceof ApiError ? e : null);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    try {
      await discussionApi.remove(id);
      comments.reload();
    } catch (e) {
      setError(e instanceof ApiError ? e : null);
    }
  };

  return (
    <section className="section" aria-labelledby="comments-title">
      <h2 id="comments-title">Questions &amp; answers</h2>
      {comments.error && (
        <ErrorNote error={comments.error} onRetry={comments.reload} />
      )}
      {comments.data?.count === 0 && (
        <p className="muted">Nobody has asked anything yet.</p>
      )}
      <ul className="comments">
        {comments.data?.results.map((comment) => (
          <li
            key={comment.id}
            className={comment.is_seller ? "comment comment-seller" : "comment"}
          >
            <p className="comment-meta">
              <strong>{comment.author ?? <em>Deleted user</em>}</strong>
              {comment.is_seller && (
                <span className="tag tag-lead">seller</span>
              )}
              <span className="muted"> · {timeAgo(comment.created_at)}</span>
              {comment.is_mine && (
                <button
                  className="link-button"
                  onClick={() => remove(comment.id)}
                >
                  Delete
                </button>
              )}
            </p>
            <p className="comment-body">{comment.body}</p>
          </li>
        ))}
      </ul>
      {comments.data && (
        <Pagination
          page={page}
          count={comments.data.count}
          onChange={setPage}
        />
      )}

      {user ? (
        <form className="form comment-form" onSubmit={submit}>
          <FormErrors messages={error?.errors.map((e) => e.message) ?? []} />
          <div className="field">
            <label htmlFor="comment">
              {isSeller ? "Answer a question" : "Ask the seller"}
            </label>
            <textarea
              id="comment"
              rows={3}
              maxLength={1000}
              required
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
          <button className="btn" disabled={busy || !body.trim()}>
            {busy ? "Posting…" : "Post"}
          </button>
        </form>
      ) : (
        <p className="muted">
          <Link to={`/login?next=${encodeURIComponent(`/lots/${listingId}`)}`}>
            Sign in
          </Link>{" "}
          to ask the seller a question.
        </p>
      )}
    </section>
  );
}
