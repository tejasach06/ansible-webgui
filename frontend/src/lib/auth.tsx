import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";
import type { Me } from "./types";

interface AuthContextValue {
  user?: Me;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<Me>;
  logout: () => Promise<void>;
  can: (perm: string) => boolean;
  canInProject: (projectId: number, perm: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { data: user, isLoading } = useQuery({ queryKey: ["me"], queryFn: () => apiFetch<Me>("/api/me"), retry: false, staleTime: 60000 });
  const value = useMemo<AuthContextValue>(() => {
    const can = (perm: string) => user?.perms.includes(perm) ?? false;
    return {
      user,
      isLoading,
      login: async (username: string, password: string) => {
        const data = await apiFetch<Me>("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
        queryClient.setQueryData(["me"], data);
        return data;
      },
      logout: async () => {
        await apiFetch("/api/auth/logout", { method: "POST" });
        queryClient.clear();
      },
      can,
      canInProject: (projectId: number, perm: string) => can("system.admin") || (user?.project_perms?.[String(projectId)]?.includes(perm) ?? false),
    };
  }, [user, isLoading, queryClient]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
