import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { accountApi } from "../api/endpoints";
import { useAuth } from "../auth/context";
import { Field, FormErrors } from "../components/Field";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

function Profile() {
  const { user, setUser } = useAuth();
  const [username, setUsername] = useState(user?.username ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [done, setDone] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setDone(false);
    try {
      setUser(
        await accountApi.update({
          username: username.trim(),
          email: email.trim(),
          current_password: password,
        }),
      );
      setPassword("");
      setDone(true);
    } catch (e) {
      setError(e instanceof ApiError ? e : null);
    }
  };

  return (
    <form className="form section" onSubmit={submit}>
      <h2>Profile</h2>
      <FormErrors messages={error?.general ?? []} />
      <Field
        label="Username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        error={error?.field("username")}
      />
      <Field
        label="Email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={error?.field("email")}
      />
      <Field
        label="Current password"
        type="password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={error?.field("current_password")}
        hint="Needed to confirm any change."
      />
      <div className="form-actions">
        <button className="btn">Save profile</button>
        {done && (
          <span className="muted small" role="status">
            Saved.
          </span>
        )}
      </div>
    </form>
  );
}

function Password() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [done, setDone] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setDone(false);
    try {
      await accountApi.changePassword(current, next);
      setCurrent("");
      setNext("");
      setDone(true);
    } catch (e) {
      setError(e instanceof ApiError ? e : null);
    }
  };

  return (
    <form className="form section" onSubmit={submit}>
      <h2>Password</h2>
      <FormErrors messages={error?.general ?? []} />
      <Field
        label="Current password"
        type="password"
        autoComplete="current-password"
        required
        value={current}
        onChange={(e) => setCurrent(e.target.value)}
        error={error?.field("current_password")}
      />
      <Field
        label="New password"
        type="password"
        autoComplete="new-password"
        required
        value={next}
        onChange={(e) => setNext(e.target.value)}
        error={error?.field("new_password")}
      />
      <div className="form-actions">
        <button className="btn">Change password</button>
        {done && (
          <span className="muted small" role="status">
            Password changed.
          </span>
        )}
      </div>
    </form>
  );
}

function DeleteAccount() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ApiError | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await accountApi.destroy(password);
      logout();
      navigate("/");
    } catch (e) {
      setError(e instanceof ApiError ? e : null);
    }
  };

  return (
    <form className="form section danger-zone" onSubmit={submit}>
      <h2>Delete account</h2>
      <p className="muted small">
        Your drafts are erased. Your finished lots, bids and comments stay in
        the record under “Deleted user”. You cannot delete the account while you
        have a live lot or hold the highest bid on a running auction.
      </p>
      <FormErrors
        messages={
          error?.errors
            .filter((e) => e.param !== "current_password")
            .map((e) => e.message) ?? []
        }
      />
      <Field
        label="Current password"
        type="password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={error?.field("current_password")}
      />
      <button className="btn btn-danger">Delete my account</button>
    </form>
  );
}

export default function Account() {
  useDocumentTitle("Account");
  return (
    <div className="narrow">
      <p className="eyebrow">Settings</p>
      <h1>Account</h1>
      <Profile />
      <Password />
      <DeleteAccount />
    </div>
  );
}
