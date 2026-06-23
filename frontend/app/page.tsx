"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { LoadingState } from "@/src/components/ui/states";
import { destinationForRole, useAuth } from "@/src/features/auth/auth-provider";

export default function Home() {
  const { user, status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
    if (status === "authenticated" && user) router.replace(destinationForRole(user.role));
  }, [router, status, user]);

  return <LoadingState label="Ouverture de HealthAI..." />;
}
