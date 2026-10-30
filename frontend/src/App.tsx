import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthProvider";
import { Layout } from "./components/Layout";
import { RequireAuth } from "./components/RequireAuth";
import { Loading } from "./components/StateNote";
import { LiveProvider } from "./live/LiveProvider";
import Catalogue from "./pages/Catalogue";
import Login from "./pages/Login";
import Lot from "./pages/Lot";
import NotFound from "./pages/NotFound";
import Register from "./pages/Register";

// Pages that only signed-in people see are loaded on demand
const LotEditor = lazy(() => import("./pages/LotEditor"));
const MyLots = lazy(() => import("./pages/MyLots"));
const MyBids = lazy(() => import("./pages/MyBids"));
const Watchlist = lazy(() => import("./pages/Watchlist"));
const Notifications = lazy(() => import("./pages/Notifications"));
const Account = lazy(() => import("./pages/Account"));

function Private({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <Suspense fallback={<Loading />}>{children}</Suspense>
    </RequireAuth>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <LiveProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Catalogue />} />
              <Route path="lots/:id" element={<Lot />} />
              <Route path="login" element={<Login />} />
              <Route path="register" element={<Register />} />
              <Route
                path="sell"
                element={
                  <Private>
                    <LotEditor />
                  </Private>
                }
              />
              <Route
                path="lots/:id/edit"
                element={
                  <Private>
                    <LotEditor />
                  </Private>
                }
              />
              <Route
                path="me/lots"
                element={
                  <Private>
                    <MyLots />
                  </Private>
                }
              />
              <Route
                path="me/bids"
                element={
                  <Private>
                    <MyBids />
                  </Private>
                }
              />
              <Route
                path="me/watching"
                element={
                  <Private>
                    <Watchlist />
                  </Private>
                }
              />
              <Route
                path="me/notifications"
                element={
                  <Private>
                    <Notifications />
                  </Private>
                }
              />
              <Route
                path="me/account"
                element={
                  <Private>
                    <Account />
                  </Private>
                }
              />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </LiveProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
