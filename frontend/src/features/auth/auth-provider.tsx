"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiRequest, configureApiAuth } from "@/src/lib/api";
import { canAccessRole, destinationForRole } from "@/src/lib/permissions";
import type { Role, User } from "@/src/types/domain";

type AuthStatus = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  user: User | null;
  accessToken: string | null;
  status: AuthStatus;
  login: (identifiant: string, motDePasse: string) => Promise<void>;
  register: (values: RegisterPayload) => Promise<void>;
  refreshUser: () => Promise<User>;
  logout: () => Promise<void>;
  canAccess: (roles: Role[]) => boolean;
};

export type RegisterPayload = {
  nom_utilisateur: string;
  email: string;
  mot_de_passe: string;
  confirmation: string;
  prenom: string;
  nom: string;
  taille_cm: number;
  poids_actuel_kg: number;
  poids_cible_kg: number;
  objectif_principal: string;
  date_cible: string;
  niveau_activite: "sedentaire" | "leger" | "modere" | "actif" | "tres_actif";
  allergies: string[];
  regime_alimentaire: string;
  contraintes_sante: string[];
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const loadCurrentUser = useCallback(async (tokenOverride?: string) => {
    const currentUser = await apiRequest<User>("/api/auth/me", {
      ...(tokenOverride ? { headers: { Authorization: `Bearer ${tokenOverride}` } } : {}),
      retry: false
    });
    setUser(currentUser);
    setStatus("authenticated");
    return currentUser;
  }, []);

  useEffect(() => {
    configureApiAuth({
      getToken: () => accessToken,
      setToken: setAccessToken,
      onUnauthorized: () => {
        setUser(null);
        setStatus("anonymous");
        if (pathname !== "/login") router.replace("/login");
      }
    });
  }, [accessToken, pathname, router]);

  useEffect(() => {
    let mounted = true;
    apiRequest<{ access_token: string }>("/api/auth/refresh", { method: "POST", auth: false, retry: false })
      .then(async (tokenPayload) => {
        if (!mounted) return;
        setAccessToken(tokenPayload.access_token);
        const currentUser = await loadCurrentUser(tokenPayload.access_token);
        if (!mounted) return;
        setUser(currentUser);
        setStatus("authenticated");
      })
      .catch(() => {
        if (!mounted) return;
        setAccessToken(null);
        setUser(null);
        setStatus("anonymous");
      });
    return () => {
      mounted = false;
    };
  }, [loadCurrentUser]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      accessToken,
      status,
      login: async (identifiant, motDePasse) => {
        const tokenPayload = await apiRequest<{ access_token: string }>("/api/auth/login", {
          method: "POST",
          auth: false,
          body: { identifiant, mot_de_passe: motDePasse }
        });
        setAccessToken(tokenPayload.access_token);
        const currentUser = await loadCurrentUser(tokenPayload.access_token);
        router.replace(destinationForRole(currentUser.role));
      },
      register: async (values) => {
        const tokenPayload = await apiRequest<{ access_token: string }>("/api/auth/register-complete", {
          method: "POST",
          auth: false,
          body: values
        });
        setAccessToken(tokenPayload.access_token);
        const currentUser = await loadCurrentUser(tokenPayload.access_token);
        router.replace(destinationForRole(currentUser.role));
      },
      refreshUser: () => loadCurrentUser(),
      logout: async () => {
        await apiRequest("/api/auth/logout", { method: "POST", auth: false }).catch(() => undefined);
        setAccessToken(null);
        setUser(null);
        setStatus("anonymous");
        router.replace("/login");
      },
      canAccess: (roles) => canAccessRole(user?.role, roles)
    }),
    [accessToken, loadCurrentUser, router, status, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}

export { destinationForRole };
