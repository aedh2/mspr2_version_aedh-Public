export type PostureStatus = "incorrect" | "almost" | "correct";
export type ExerciseType = "dynamic" | "static";
export type ExerciseId = "squat" | "curl_biceps" | "push_up" | "gainage" | "wall_sit" | "tree_pose";
export type MovementPhase = "phase_initiale" | "phase_contractee";
export type ObservedMovementPhase = MovementPhase | "phase_transition";
export type DetectionStatus = "none" | "partial" | "detected";
export type HandGesture = "ok" | "pause" | "peace" | null;
export type PoseLandmarkName =
  | "left_shoulder"
  | "right_shoulder"
  | "left_elbow"
  | "right_elbow"
  | "left_wrist"
  | "right_wrist"
  | "left_hip"
  | "right_hip"
  | "left_knee"
  | "right_knee"
  | "left_ankle"
  | "right_ankle";

export type PosePoint = {
  x: number;
  y: number;
  visibility?: number;
};

export type PoseLandmarks = Partial<Record<PoseLandmarkName, PosePoint>>;
export type HandLandmarks = PosePoint[];

export type HandDetection = {
  landmarks: HandLandmarks[];
  gesture: HandGesture;
};

export type ExerciseConfig = {
  id: ExerciseId;
  name: string;
  type: ExerciseType;
  trackedJoints: string[];
  requiredLandmarks: PoseLandmarkName[];
  targetRepsPerSet: number;
  instructions: string[];
  correctThreshold: number;
  almostThreshold: number;
  guide: PoseLandmarks;
};

export type PostureSession = {
  reps: number;
  repsInCurrentSet: number;
  sets: number;
  holdSeconds: number;
  bestHoldSeconds: number;
  validatedHolds: number[];
  phase: MovementPhase;
  status: PostureStatus;
  lastRepAt: number;
  lastValidAt: number | null;
};

export type PostureEvaluation = {
  status: PostureStatus;
  score: number;
  angles: Record<string, number>;
  detectedErrors: string[];
  session: PostureSession;
  observedPhase: ObservedMovementPhase;
  detectionStatus: Exclude<DetectionStatus, "none">;
  missingLandmarks: PoseLandmarkName[];
};

export type CoachPostureFeedbackRequest = {
  exercise: ExerciseId;
  status: PostureStatus;
  angles: Record<string, number>;
  detected_errors: string[];
  reps: number;
  reps_in_current_set: number;
  sets: number;
  hold_seconds: number;
  best_hold_seconds: number;
  validated_holds: number[];
  score_alignement: number;
  person_detected: boolean;
};

export type CoachPostureFeedback = {
  mode: "local" | "external";
  exercise: ExerciseId;
  statut_posture: PostureStatus;
  erreurs_principales: string[];
  conseils: string[];
  safety_warning: string;
  encouragement: string;
  repetitions: number;
  sets: number;
  chrono: number;
  score_alignement: number;
};

export type CoachPostureValidationRequest = {
  exercise: ExerciseId;
  exercise_label: string;
  type: ExerciseType;
  reps: number;
  reps_in_current_set: number;
  sets: number;
  hold_seconds: number;
  best_hold_seconds: number;
  validated_holds: number;
  score_alignement: number;
  status: PostureStatus;
  detected_errors: string[];
  feedback?: Record<string, unknown>;
  snapshot_base64?: string | null;
  validated_at?: string;
};

export type CoachPostureValidationItem = {
  coach_posture_id: number;
  exercise: string;
  exercise_label: string;
  type: ExerciseType;
  status: PostureStatus;
  score_alignement: number;
  reps: number;
  reps_in_current_set: number;
  sets: number;
  hold_seconds: number;
  best_hold_seconds: number;
  validated_holds: number;
  snapshot_path?: string | null;
  validated_at: string;
};

export type CoachPostureValidationResponse = {
  validation_id: string;
  message: string;
  exercise: string;
  saved: boolean;
  seance_id?: number | null;
  seance_exercice_id?: number | null;
  item: CoachPostureValidationItem;
  summary: {
    exercise?: ExerciseId | string | null;
    type?: ExerciseType | null;
    reps: number;
    reps_in_current_set: number;
    sets: number;
    hold_seconds: number;
    score_alignement: number;
  };
};

export type CoachPostureHistoryItem = CoachPostureValidationResponse & {
  validated_at: string;
  exercise_label: string;
  type: ExerciseType;
  status: PostureStatus;
  detected_errors: string[];
  snapshot_path?: string | null;
  snapshot_data_url?: string | null;
};
