import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/context";
import { useLive } from "../live/context";
import { Toasts } from "./Toasts";

function useTheme(): [string, () => void] {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("commerce.theme") ?? "system";
    } catch {
      return "system";
    }
  });
  useEffect(() => {
    if (theme === "system")
      document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("commerce.theme", theme);
    } catch {
      /* ignore */
    }
  }, [theme]);
  const next = () =>
    setTheme((t) =>
      t === "system" ? "dark" : t === "dark" ? "light" : "system",
    );
  return [theme, next];
}

function UserMenu() {
  const { user, logout } = useAuth();
  const { summary } = useLive();
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);

  // Close on a click outside or Escape (a click inside the menu closes it too, see onClick below)
  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) =>
      event.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null;
  const outbid = summary?.bids.outbid ?? 0;
  return (
    <div className="user-menu" ref={wrapper}>
      <button
        className="user-button"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen(!open)}
      >
        <span className="avatar" aria-hidden="true">
          {user.username[0].toUpperCase()}
        </span>
        {user.username}
        {outbid > 0 && (
          <span
            className="badge badge-alert"
            title="Lots where you were outbid"
          >
            {outbid}
          </span>
        )}
      </button>
      {open && (
        <div className="menu" role="menu" onClick={() => setOpen(false)}>
          <Link role="menuitem" to="/me/bids">
            My bids{" "}
            {outbid > 0 && (
              <span className="badge badge-alert">{outbid} outbid</span>
            )}
          </Link>
          <Link role="menuitem" to="/me/lots">
            My lots
          </Link>
          <Link role="menuitem" to="/me/watching">
            Watchlist{" "}
            {summary && summary.watching > 0 && (
              <span className="badge">{summary.watching}</span>
            )}
          </Link>
          <Link role="menuitem" to="/me/notifications">
            Notifications
          </Link>
          <Link role="menuitem" to="/me/account">
            Account
          </Link>
          <button role="menuitem" onClick={logout}>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export function Layout() {
  const { user } = useAuth();
  const { summary } = useLive();
  const [theme, nextTheme] = useTheme();
  const unread = summary?.unread_notifications ?? 0;
  const location = useLocation();
  const onCatalogue = location.pathname === "/";
  const closedSales =
    new URLSearchParams(location.search).get("status") === "ended";

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="masthead">
        <div className="masthead-top">
          <span className="muted small">
            Timed auctions · every lot closes on the clock
          </span>
          <button
            className="btn btn-quiet small"
            onClick={nextTheme}
            aria-label={`Theme: ${theme}. Click to change`}
          >
            {theme === "dark"
              ? "☾ Dark"
              : theme === "light"
                ? "☀ Light"
                : "◐ Auto"}
          </button>
        </div>
        <Link to="/" className="wordmark">
          Commerce
        </Link>
        <p className="tagline">Auctions of curious &amp; beautiful things</p>
        <nav className="main-nav" aria-label="Main">
          <div className="nav-links">
            <Link
              to="/"
              className={onCatalogue && !closedSales ? "active" : undefined}
            >
              Catalogue
            </Link>
            <Link
              to="/?status=ended"
              className={onCatalogue && closedSales ? "active" : undefined}
            >
              Closed sales
            </Link>
            <NavLink to="/sell">Sell a lot</NavLink>
          </div>
          <div className="nav-user">
            {user ? (
              <>
                <Link
                  to="/me/notifications"
                  className="bell"
                  aria-label={`Notifications, ${unread} unread`}
                >
                  <span aria-hidden="true">🔔</span>
                  {unread > 0 && (
                    <span className="badge badge-alert">{unread}</span>
                  )}
                </Link>
                <UserMenu />
              </>
            ) : user === null ? (
              <>
                <Link to="/login" className="btn btn-quiet">
                  Sign in
                </Link>
                <Link to="/register" className="btn">
                  Create account
                </Link>
              </>
            ) : null}
          </div>
        </nav>
      </header>
      <main id="main" className="page">
        <Outlet />
      </main>
      <footer className="footer">
        <p>
          Commerce · bids are binding · the highest bid at the close wins,
          unless the reserve was not met.
        </p>
      </footer>
      <Toasts />
    </>
  );
}
