"use client";

import { useParams } from "next/navigation";
import { ExerciceDetailPage } from "@/src/features/me/me-pages";

export default function Page() {
  const params = useParams<{ id: string }>();
  return <ExerciceDetailPage id={params?.id || ""} />;
}
