import { apiRequest } from "@/src/lib/api";
import type { MealAnalysisConfig, MealAnalysisResult } from "@/src/types/domain";

export function analyzeMealPhoto(imageBase64: string, mimeType?: string | null) {
  return apiRequest<MealAnalysisResult>("/api/me/analyse-plat", {
    method: "POST",
    body: {
      image_base64: imageBase64,
      mime_type: mimeType || null
    }
  });
}

export function getMealAnalysisConfig() {
  return apiRequest<MealAnalysisConfig>("/api/me/analyse-plat/config");
}
