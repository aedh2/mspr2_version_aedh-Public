"use client";

import { AppShell } from "@/src/components/app-shell";
import { RoleGuard } from "@/src/components/role-guard";

export default function MeLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGuard roles={["UTILISATEUR"]}>
      <AppShell>{children}</AppShell>
    </RoleGuard>
  );
}
