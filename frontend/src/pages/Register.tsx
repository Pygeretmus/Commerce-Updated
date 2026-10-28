import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/context";
import { Field, FormErrors } from "../components/Field";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { safeNext } from "../navigation";

export default function Register() {
  useDocumentTitle("Create account");
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={next} replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register(username.trim(), email.trim(), password);
      navigate(next, { replace: true });
    } catch (e) {
      setError(e instanceof ApiError ? e : null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="narrow">
      <p className="eyebrow">Join the room</p>
      <h1>Create an account</h1>
      <form className="form" onSubmit={submit}>
        <FormErrors messages={error?.general ?? []} />
        <Field
          label="Username"
          autoComplete="username"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          error={error?.field("username")}
          hint="Others see only the first and last letters of it in bid histories."
        />
        <Field
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={error?.field("email")}
          hint="Never shown to anybody."
        />
        <Field
          label="Password"
          type="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={error?.field("password")}
        />
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
      <p className="muted">
        Already registered?{" "}
        <Link to={`/login?next=${encodeURIComponent(next)}`}>Sign in</Link>
      </p>
    </div>
  );
}
