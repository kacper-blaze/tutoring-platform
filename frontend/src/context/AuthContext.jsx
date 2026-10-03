import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "../api/client";
import { clearSession, getRole, isAuthenticated, setSession } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [role, setRole] = useState(getRole());
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(isAuthenticated());

  const loadUser = useCallback(async () => {
    if (!isAuthenticated()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.get("/users/me");
      setUser(me);
      setRole(me.role);
    } catch {
      clearSession();
      setUser(null);
      setRole(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  async function login(email, password) {
    const data = await api.post("/auth/login", { email, password }, { auth: false });
    setSession(data);
    setRole(data.role);
    await loadUser();
    return data;
  }

  function logout() {
    clearSession();
    setUser(null);
    setRole(null);
  }

  const value = { user, role, loading, login, logout, refresh: loadUser };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth musi być użyty wewnątrz <AuthProvider>");
  return ctx;
}
