"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/src/lib/api";
import type { Exercice, ExerciceFilters } from "@/src/types/domain";

export function useExerciceFilters() {
  return useQuery({
    queryKey: ["/api/exercices/filters"],
    staleTime: 60_000,
    queryFn: () =>
      apiRequest<ExerciceFilters>("/api/exercices/filters")
  });
}

export function useExercice(id: number | string | undefined) {
  return useQuery({
    enabled: id !== undefined && id !== "",
    queryKey: ["/api/exercices", String(id)],
    queryFn: () => apiRequest<Exercice>(`/api/exercices/${id}`)
  });
}
