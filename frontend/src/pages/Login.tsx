import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/context";
import { Field, FormErrors } from "../components/Field";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { safeNext } from "../navigation";

export default function Login() {
  useDocumentTitle("Sign in");
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={next} replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
      navigate(next, { replace: true });
    } catch (e) {
      setError(e instanceof ApiError ? e : null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="narrow">
      <p className="eyebrow">Welcome back</p>
      <h1>Sign in</h1>
      <form className="form" onSubmit={submit}>
        <FormErrors
          messages={
            error
              ? error.status === 401
                ? ["The username or the password is wrong."]
                : error.errors.map((e) => e.message)
              : []
          }
        />
        <Field
          label="Username"
          autoComplete="username"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <Field
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="muted">
        New here?{" "}
        <Link to={`/register?next=${encodeURIComponent(next)}`}>
          Create an account
        </Link>
      </p>
    </div>
  );
}
