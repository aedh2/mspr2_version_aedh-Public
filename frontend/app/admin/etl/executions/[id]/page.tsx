"use client";

import { useParams } from "next/navigation";
import { EtlExecutionDetailPage } from "@/src/features/admin/admin-pages";

export default function Page() {
  const params = useParams<{ id: string }>();
  return <EtlExecutionDetailPage id={params?.id || ""} />;
}
