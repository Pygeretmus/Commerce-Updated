import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { accountApi } from "../api/endpoints";
import { hasTokens, onForcedLogout, saveTokens } from "../api/client";
import type { Account } from "../api/types";
import { AuthContext } from "./context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Account | null | undefined>(() =>
    hasTokens() ? undefined : null,
  );

  // Restore the session from stored tokens
  useEffect(() => {
    if (!hasTokens()) return;
    accountApi
      .me()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  // The API client signs the user out when the refresh token stops working
  useEffect(() => onForcedLogout(() => setUser(null)), []);

  const login = useCallback(async (username: string, password: string) => {
    await accountApi.login(username, password);
    setUser(await accountApi.me());
  }, []);

  const register = useCallback(
    async (username: string, email: string, password: string) => {
      await accountApi.register(username, email, password);
      await login(username, password);
    },
    [login],
  );

  const logout = useCallback(() => {
    saveTokens(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, login, register, logout, setUser }),
    [user, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
