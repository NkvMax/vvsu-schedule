import {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

import type { ReactNode } from "react";

interface AuthContext {
  token: string | null;
  login: (t: string) => void;
  logout: () => void;
}

const AuthCtx = createContext<AuthContext | null>(null);
export const useAuth = () => useContext(AuthCtx)!;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("token") || null
  );

  /* логин / логаут */
  const login = (t: string) => {
    localStorage.setItem("token", t);
    setToken(t);
  };
  const logout = () => {
    localStorage.removeItem("token");
    setToken(null);
  };

  /* подставляем Authorization ко всем fetch */
  useEffect(() => {
    const nativeFetch = window.fetch.bind(window);

    window.fetch = (input: RequestInfo | URL, init: RequestInit = {}) => {
      const headers = new Headers(init.headers);
      if (token) headers.set("Authorization", `Bearer ${token}`);
      return nativeFetch(input, { ...init, headers });
    };

    /* откат при размонтировании или смене токена */
    return () => {
      window.fetch = nativeFetch;
    };
  }, [token]);

  return (
    <AuthCtx.Provider value={{ token, login, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}
