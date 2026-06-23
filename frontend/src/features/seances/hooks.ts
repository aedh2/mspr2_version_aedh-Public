"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/src/lib/api";
import type { Seance, SeanceExercice, SeancesFilters } from "@/src/types/domain";

export function useSeancesFilters() {
  return useQuery({
    queryKey: ["/api/me/seances/filters"],
    staleTime: 60_000,
    queryFn: () =>
      apiRequest<SeancesFilters>("/api/me/seances/filters")
  });
}

export function useSeance(id: number | string | undefined) {
  return useQuery({
    enabled: id !== undefined && id !== "",
    queryKey: ["me-seance", String(id)],
    queryFn: () => apiRequest<Seance>(`/api/me/seances/${id}`)
  });
}

export function useSeanceExercices(id: number | string | undefined) {
  return useQuery({
    enabled: id !== undefined && id !== "",
    queryKey: ["me-seance-exercices", String(id)],
    queryFn: () => apiRequest<SeanceExercice[]>(`/api/me/seances/${id}/exercices`)
  });
}
