import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiRequest } from "../lib/api";
import type { AuthUser, LoginResponse } from "../lib/types";

interface AuthContextValue {
  user: AuthUser | null;
  accessToken: string | null;
  login: (email: string, password: string, otpCode?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readUser(): AuthUser | null {
  try {
    const value = sessionStorage.getItem("deverp.user");
    return value ? (JSON.parse(value) as AuthUser) : null;
  } catch {
    sessionStorage.removeItem("deverp.user");
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(readUser);
  const [accessToken, setAccessToken] = useState<string | null>(() =>
    sessionStorage.getItem("deverp.access"),
  );
  useEffect(() => {
    const clearSession = () => {
      setAccessToken(null);
      setUser(null);
    };
    window.addEventListener("deverp:session-expired", clearSession);
    return () =>
      window.removeEventListener("deverp:session-expired", clearSession);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      accessToken,
      async login(email, password, otpCode) {
        const response = await apiRequest<LoginResponse>("/auth/login/", {
          method: "POST",
          body: JSON.stringify({
            email,
            password,
            ...(otpCode ? { otp_code: otpCode } : {}),
          }),
        });
        sessionStorage.setItem("deverp.access", response.access);
        sessionStorage.setItem("deverp.refresh", response.refresh);
        sessionStorage.setItem("deverp.user", JSON.stringify(response.user));
        setAccessToken(response.access);
        setUser(response.user);
      },
      async refreshUser() {
        const refreshed = await apiRequest<AuthUser>("/users/me/", {}, accessToken);
        sessionStorage.setItem("deverp.user", JSON.stringify(refreshed));
        setUser(refreshed);
      },
      async logout() {
        const refresh = sessionStorage.getItem("deverp.refresh");
        try {
          if (refresh) {
            await apiRequest<void>(
              "/auth/logout/",
              {
                method: "POST",
                body: JSON.stringify({ refresh }),
              },
              accessToken,
            );
          }
        } finally {
          sessionStorage.removeItem("deverp.access");
          sessionStorage.removeItem("deverp.refresh");
          sessionStorage.removeItem("deverp.user");
          setAccessToken(null);
          setUser(null);
        }
      },
    }),
    [user, accessToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider.");
  return value;
}
