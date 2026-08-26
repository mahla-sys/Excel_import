import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "../api/client";
import type { Me } from "../api/types";

interface AuthContextValue {
  user: Me | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  const { data: user, isLoading } = useQuery<Me | null>({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await apiRequest<Me>("/auth/me/");
      } catch (err) {
        // 401/403 simply means not logged in; not an error to surface here.
        return null;
      }
    },
    staleTime: 60_000,
  });

  const login = useCallback(
    async (username: string, password: string) => {
      setIsAuthenticating(true);
      try {
        await apiRequest("/auth/login/", {
          method: "POST",
          body: { username, password },
        });
        await queryClient.invalidateQueries({ queryKey: ["me"] });
      } finally {
        setIsAuthenticating(false);
      }
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await apiRequest("/auth/logout/", { method: "POST" });
    } finally {
      queryClient.clear();
      // Hard navigation clears any in-memory state.
      window.location.href = "/login";
    }
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: user ?? null,
      isLoading: isLoading || isAuthenticating,
      isAuthenticated: Boolean(user),
      login,
      logout,
    }),
    [user, isLoading, isAuthenticating, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
