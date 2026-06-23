"use client";

import { useParams } from "next/navigation";
import { AdminUserDetailPage } from "@/src/features/admin/admin-pages";

export default function Page() {
  const params = useParams<{ id: string }>();
  return <AdminUserDetailPage id={params?.id || ""} />;
}
