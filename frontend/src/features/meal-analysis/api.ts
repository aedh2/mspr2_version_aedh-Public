import { apiRequest, getAuthToken } from "@/src/lib/api";
import type { MealAnalysisConfig, MealAnalysisResult } from "@/src/types/domain";

type GeminiFood = {
  name: string;
  confidence: number;
  quantity_g?: number | null;
  macros?: {
    calories: number;
    proteins_g: number;
    carbs_g: number;
    fats_g: number;
    fiber_g: number;
  } | null;
};

type GeminiResponse = {
  foods: GeminiFood[];
  total_macros: {
    calories: number;
    proteins_g: number;
    carbs_g: number;
    fats_g: number;
    fiber_g: number;
  };
  source: string;
  error?: string | null;
};

function geminiToMealResult(data: GeminiResponse): MealAnalysisResult {
  const foods = data.foods || [];
  const avgConfidence = foods.length
    ? foods.reduce((sum, f) => sum + (f.confidence || 0), 0) / foods.length
    : 0;

  return {
    plat_detecte: foods[0]?.name || "Repas analysé",
    commentaire: `${foods.length} aliment(s) détecté(s) par Gemini Vision`,
    confidence: avgConfidence,
    source_analyse: (data.source || "gemini-2.5-flash") as MealAnalysisResult["source_analyse"],
    mode: "external",
    calories_estimees: data.total_macros?.calories ?? 0,
    macronutriments: {
      proteines_g: data.total_macros?.proteins_g ?? 0,
      glucides_g: data.total_macros?.carbs_g ?? 0,
      lipides_g: data.total_macros?.fats_g ?? 0
    },
    aliments_detectes: foods.map((f) => ({
      nom: f.name,
      confidence: f.confidence,
      label_source: "gemini-vision",
      matched_aliment_nom: null,
      matched_aliment_id: null,
      portion_estimee: f.quantity_g != null ? `${f.quantity_g} g` : null,
      calories_kcal: f.macros?.calories ?? null,
      proteines_g: f.macros?.proteins_g ?? null,
      glucides_g: f.macros?.carbs_g ?? null,
      lipides_g: f.macros?.fats_g ?? null,
      details: null
    })),
    portions_estimees: foods
      .filter((f) => f.quantity_g != null)
      .map((f) => ({
        nom: f.name,
        portion: `${f.quantity_g} g`,
        grammes_estimes: f.quantity_g as number
      })),
    hypotheses: [],
    limites_estimation: [
      "Estimation basée sur la vision IA — les portions sont approximatives.",
      "Les macros sont calculées sur des valeurs moyennes par aliment."
    ],
    raw_vision_predictions: []
  };
}

export async function analyzeMealPhoto(imageBase64: string, mimeType?: string | null): Promise<MealAnalysisResult> {
  const base64Data = imageBase64.includes(",") ? imageBase64.split(",")[1] : imageBase64;
  const mime = mimeType || "image/jpeg";
  const binary = atob(base64Data);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: mime });

  const formData = new FormData();
  formData.append("image", blob, "repas.jpg");

  const token = getAuthToken();
  const response = await fetch("/api/ai/analyse-repas", {
    method: "POST",
    credentials: "include",
    headers: token ? { authorization: `Bearer ${token}` } : {},
    body: formData
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const msg = (error as { detail?: string; error?: { message?: string } })?.error?.message
      || (error as { detail?: string })?.detail
      || `Erreur ${response.status}`;
    throw new Error(msg);
  }

  const data = (await response.json()) as GeminiResponse;
  return geminiToMealResult(data);
}

export function getMealAnalysisConfig() {
  return apiRequest<MealAnalysisConfig>("/api/me/analyse-plat/config");
}
