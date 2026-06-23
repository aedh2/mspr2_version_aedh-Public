from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PostureStatus = Literal["incorrect", "almost", "correct"]
ExerciseType = Literal["dynamic", "static"]


class CoachPostureFeedbackRequest(BaseModel):
    exercise: str = Field(..., min_length=1)
    status: PostureStatus
    angles: dict[str, float] = Field(default_factory=dict)
    detected_errors: list[str] = Field(default_factory=list)
    reps: int = Field(default=0, ge=0)
    reps_in_current_set: int = Field(default=0, ge=0)
    sets: int = Field(default=0, ge=0)
    hold_seconds: int = Field(default=0, ge=0)
    best_hold_seconds: int = Field(default=0, ge=0)
    validated_holds: list[int] = Field(default_factory=list)
    score_alignement: int = Field(default=0, ge=0, le=100)
    person_detected: bool = True


class CoachPostureFeedbackResponse(BaseModel):
    mode: Literal["local", "external"] = "local"
    exercise: str
    statut_posture: PostureStatus
    erreurs_principales: list[str] = Field(default_factory=list)
    conseils: list[str] = Field(default_factory=list)
    safety_warning: str = "Arrete l'exercice en cas de douleur."
    encouragement: str = "Bonne progression, continue."
    repetitions: int = 0
    sets: int = 0
    chrono: int = 0
    score_alignement: int = 0


class CoachPostureValidationRequest(BaseModel):
    exercise: str = Field(..., min_length=1)
    exercise_label: str = Field(..., min_length=1)
    type: ExerciseType
    reps: int = Field(default=0, ge=0)
    reps_in_current_set: int = Field(default=0, ge=0)
    sets: int = Field(default=0, ge=0)
    hold_seconds: int = Field(default=0, ge=0)
    best_hold_seconds: int = Field(default=0, ge=0)
    validated_holds: int | list[int] = Field(default=0)
    score_alignement: int = Field(default=0, ge=0, le=100)
    status: PostureStatus
    detected_errors: list[str] = Field(default_factory=list)
    feedback: dict[str, Any] = Field(default_factory=dict)
    snapshot_base64: str | None = Field(default=None, max_length=6_000_000)
    validated_at: datetime | None = None


class CoachPostureValidationSummary(BaseModel):
    exercise: str | None = None
    type: ExerciseType | None = None
    reps: int = 0
    reps_in_current_set: int = 0
    sets: int = 0
    hold_seconds: int = 0
    score_alignement: int = 0


class CoachPostureValidationItem(BaseModel):
    coach_posture_id: int
    exercise: str
    exercise_label: str
    type: ExerciseType
    status: PostureStatus
    score_alignement: int
    reps: int
    reps_in_current_set: int = 0
    sets: int
    hold_seconds: int
    best_hold_seconds: int = 0
    validated_holds: int = 0
    snapshot_path: str | None = None
    validated_at: datetime


class CoachPostureValidationResponse(BaseModel):
    validation_id: str
    message: str = "Exercice enregistre"
    exercise: str
    saved: bool = True
    seance_id: int | None = None
    seance_exercice_id: int | None = None
    item: CoachPostureValidationItem
    summary: CoachPostureValidationSummary


class CoachPostureHistoryItem(CoachPostureValidationResponse):
    validated_at: datetime
    exercise_label: str
    type: ExerciseType
    status: PostureStatus
    detected_errors: list[str] = Field(default_factory=list)
    snapshot_path: str | None = None
