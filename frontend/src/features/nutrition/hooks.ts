"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/src/lib/api";
import type { NutritionCharts, Plat, PlatLigne } from "@/src/types/domain";

export function useNutritionCharts(granularity: "day" | "week" | "month" = "day") {
  return useQuery({
    queryKey: ["me-nutrition-charts", granularity],
    queryFn: () => apiRequest<NutritionCharts>(`/api/me/nutrition/charts`, { query: { granularity } })
  });
}

export function usePlat(id: number | string | undefined) {
  return useQuery({
    enabled: id !== undefined && id !== "",
    queryKey: ["me-plat", String(id)],
    queryFn: () => apiRequest<Plat>(`/api/me/plats/${id}`)
  });
}

export function usePlatLignes(id: number | string | undefined) {
  return useQuery({
    enabled: id !== undefined && id !== "",
    queryKey: ["me-plat-lignes", String(id)],
    queryFn: () => apiRequest<PlatLigne[]>(`/api/me/plats/${id}/lignes`)
  });
}
