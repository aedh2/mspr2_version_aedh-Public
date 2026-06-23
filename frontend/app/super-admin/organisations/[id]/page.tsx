"use client";

import { useParams } from "next/navigation";
import { SuperAdminOrganisationDetailPage } from "@/src/features/super-admin/super-admin-pages";

export default function Page() {
  const params = useParams<{ id: string }>();
  return <SuperAdminOrganisationDetailPage organisationId={Number(params?.id || 0)} />;
}
