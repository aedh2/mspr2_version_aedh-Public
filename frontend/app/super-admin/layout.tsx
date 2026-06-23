"use client";

import { AppShell } from "@/src/components/app-shell";
import { RoleGuard } from "@/src/components/role-guard";

export default function SuperAdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGuard roles={["SUPER_ADMIN"]}>
      <AppShell>{children}</AppShell>
    </RoleGuard>
  );
}
