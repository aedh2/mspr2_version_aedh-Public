"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { LoadingState } from "@/src/components/ui/states";
import { useAuth } from "@/src/features/auth/auth-provider";
import type { Role } from "@/src/types/domain";

export function RoleGuard({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const { user, status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "anonymous") {
      router.replace("/login");
      return;
    }
    if (status === "authenticated" && (!user || !roles.includes(user.role))) {
      router.replace(user?.role === "UTILISATEUR" ? "/me/dashboard" : "/admin/dashboard");
    }
  }, [roles, router, status, user]);

  if (status === "loading") {
    return <LoadingState label="Verification de la session..." />;
  }

  if (!user || !roles.includes(user.role)) {
    return <LoadingState label="Redirection..." />;
  }

  return <>{children}</>;
}
