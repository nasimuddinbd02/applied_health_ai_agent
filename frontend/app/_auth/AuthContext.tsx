"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/providers/apiProvider";
import type { AuthUser, PatientSignup } from "@/models/types";

const TOKEN_KEY = "ch_token";

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  signup: (body: PatientSignup) => Promise<AuthUser>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

async function syncCookie(token: string | null) {
  if (token) {
    await fetch("/api/session", { method: "POST", body: JSON.stringify({ token }) });
  } else {
    await fetch("/api/session", { method: "DELETE" });
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
    if (!token) {
      setLoading(false);
      return;
    }
    api.setToken(token);
    api.me()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        api.setToken(null);
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const { access_token, user } = await api.login(email, password);
    localStorage.setItem(TOKEN_KEY, access_token);
    api.setToken(access_token);
    await syncCookie(access_token);
    setUser(user);
    return user;
  }

  async function signup(body: PatientSignup) {
    const { access_token, user } = await api.signup(body);
    localStorage.setItem(TOKEN_KEY, access_token);
    api.setToken(access_token);
    await syncCookie(access_token);
    setUser(user);
    return user;
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    api.setToken(null);
    void syncCookie(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

// Landing page per role once logged in.
export function landingPathFor(user: AuthUser): string {
  if (user.role === "patient" && user.patient_id) return `/patients/${user.patient_id}`;
  if (user.role === "admin") return "/admin";
  if (user.role === "receptionist") return "/reception";
  return "/";
}
