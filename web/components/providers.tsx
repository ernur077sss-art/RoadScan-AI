"use client";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { api, ApiError, type User, type Health } from "@/lib/api";
type Auth = {
  user: User | null;
  loading: boolean;
  error: string;
  health: Health | null;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};
const Context = createContext<Auth | null>(null);
export function Providers({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [health, setHealth] = useState<Health | null>(null);
  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setUser(await api<User>("/auth/me"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setUser(null);
      else setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
    api<Health>("/health")
      .then(setHealth)
      .catch(() => {});
    if ("serviceWorker" in navigator)
      navigator.serviceWorker.register("/sw.js").catch(() => {});
  }, [refresh]);
  async function logout() {
    await api("/auth/logout", { method: "POST" });
    setUser(null);
  }
  return (
    <Context.Provider value={{ user, loading, error, health, refresh, logout }}>
      {children}
    </Context.Provider>
  );
}
export function useAuth() {
  const v = useContext(Context);
  if (!v) throw new Error("Missing auth provider");
  return v;
}
