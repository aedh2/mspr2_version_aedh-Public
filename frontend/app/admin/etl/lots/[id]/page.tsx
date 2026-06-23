"use client";

import { useParams } from "next/navigation";
import { EtlLotDetailPage } from "@/src/features/admin/admin-pages";

export default function Page() {
  const params = useParams<{ id: string }>();
  return <EtlLotDetailPage id={params?.id || ""} />;
}
