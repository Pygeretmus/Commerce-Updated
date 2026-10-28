import { createContext, useContext } from "react";
import type { Account } from "../api/types";

export interface AuthState {
  /** undefined while the session is being restored, null when nobody is signed in */
  user: Account | null | undefined;
  login: (username: string, password: string) => Promise<void>;
  register: (
    username: string,
    email: string,
    password: string,
  ) => Promise<void>;
  logout: () => void;
  setUser: (user: Account | null) => void;
}

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}
