import { apiRequest } from "@/src/lib/api";
import type {
  CoachPostureFeedback,
  CoachPostureFeedbackRequest,
  CoachPostureHistoryItem,
  CoachPostureValidationRequest,
  CoachPostureValidationResponse
} from "./types";

export function requestCoachPostureFeedback(payload: CoachPostureFeedbackRequest) {
  return apiRequest<CoachPostureFeedback>("/api/me/coach-posture/feedback", {
    method: "POST",
    body: payload
  });
}

export function validateCoachPostureExercise(payload: CoachPostureValidationRequest) {
  return apiRequest<CoachPostureValidationResponse>("/api/me/coach-posture/validate", {
    method: "POST",
    body: payload
  });
}

export function getCoachPostureHistory() {
  return apiRequest<CoachPostureHistoryItem[]>("/api/me/coach-posture/history");
}
