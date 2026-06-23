"use client";

import { AppShell } from "@/src/components/app-shell";
import { RoleGuard } from "@/src/components/role-guard";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGuard roles={["ADMIN", "SUPER_ADMIN"]}>
      <AppShell>{children}</AppShell>
    </RoleGuard>
  );
}
