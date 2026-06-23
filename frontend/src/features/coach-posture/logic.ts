import type {
  ExerciseConfig,
  ExerciseId,
  ObservedMovementPhase,
  PoseLandmarkName,
  PoseLandmarks,
  PosePoint,
  PostureEvaluation,
  PostureSession,
  PostureStatus
} from "./types";

const REP_COOLDOWN_MS = 650;

export function createInitialPostureSession(): PostureSession {
  return {
    reps: 0,
    repsInCurrentSet: 0,
    sets: 0,
    holdSeconds: 0,
    bestHoldSeconds: 0,
    validatedHolds: [],
    phase: "phase_initiale",
    status: "incorrect",
    lastRepAt: 0,
    lastValidAt: null
  };
}

export function createInitialExerciseSessions(): Record<ExerciseId, PostureSession> {
  return {
    squat: createInitialPostureSession(),
    curl_biceps: createInitialPostureSession(),
    push_up: createInitialPostureSession(),
    gainage: createInitialPostureSession(),
    wall_sit: createInitialPostureSession(),
    tree_pose: createInitialPostureSession()
  };
}

export function validateStaticHold(previous: PostureSession): PostureSession {
  const roundedHold = Math.max(0, previous.holdSeconds);
  if (roundedHold <= 0) {
    return previous;
  }
  const validatedHolds = [...previous.validatedHolds, roundedHold];
  return {
    ...previous,
    holdSeconds: 0,
    bestHoldSeconds: Math.max(previous.bestHoldSeconds, roundedHold),
    validatedHolds,
    sets: validatedHolds.length,
    repsInCurrentSet: 0,
    phase: "phase_initiale",
    status: "incorrect",
    lastRepAt: 0,
    lastValidAt: null
  };
}

export function evaluatePosture(
  exercise: ExerciseConfig,
  landmarks: PoseLandmarks,
  previous: PostureSession,
  deltaSeconds: number,
  timestampMs = 0
): PostureEvaluation {
  const angles = calculateAngles(landmarks);
  const missingLandmarks = requiredMissingLandmarks(exercise, landmarks);
  const hasRequiredLandmarks = missingLandmarks.length === 0;
  const score = hasRequiredLandmarks ? scoreExercise(exercise.id, landmarks, angles) : 0;
  const status = hasRequiredLandmarks ? statusFromScore(score, exercise) : "incorrect";
  const detectedErrors = hasRequiredLandmarks
    ? detectErrors(exercise.id, landmarks, angles, status)
    : missingLandmarksError(missingLandmarks);
  const observedPhase = hasRequiredLandmarks ? observedMovementPhase(exercise.id, landmarks, angles) : "phase_transition";
  const session = exercise.type === "static"
    ? advanceStaticSession(previous, status, deltaSeconds, hasRequiredLandmarks && score >= exercise.correctThreshold, timestampMs)
    : advanceDynamicSession(previous, observedPhase, status, exercise.targetRepsPerSet, timestampMs, hasRequiredLandmarks);

  return {
    status,
    score,
    angles,
    detectedErrors,
    observedPhase,
    session: { ...session, status },
    detectionStatus: hasRequiredLandmarks ? "detected" : "partial",
    missingLandmarks
  };
}

export function advanceDynamicSession(
  previous: PostureSession,
  observedPhase: ObservedMovementPhase,
  status: PostureStatus,
  targetRepsPerSet: number,
  timestampMs = 0,
  canCount = true
): PostureSession {
  if (!canCount || observedPhase === "phase_transition") {
    return { ...previous, status };
  }

  if (status === "incorrect") {
    return {
      ...previous,
      phase: observedPhase === "phase_initiale" ? "phase_initiale" : previous.phase,
      status
    };
  }

  if (previous.phase === "phase_initiale" && observedPhase === "phase_contractee") {
    return { ...previous, phase: "phase_contractee", status };
  }

  if (previous.phase === "phase_contractee" && observedPhase === "phase_initiale") {
    if (previous.lastRepAt > 0 && timestampMs > 0 && timestampMs - previous.lastRepAt < REP_COOLDOWN_MS) {
      return { ...previous, phase: "phase_initiale", status };
    }
    const reps = previous.reps + 1;
    const nextRepsInSet = previous.repsInCurrentSet + 1;
    const completedSet = nextRepsInSet >= targetRepsPerSet;
    return {
      ...previous,
      reps,
      repsInCurrentSet: completedSet ? 0 : nextRepsInSet,
      sets: completedSet ? previous.sets + 1 : previous.sets,
      phase: "phase_initiale",
      status,
      lastRepAt: timestampMs
    };
  }

  return { ...previous, status };
}

export function advanceStaticSession(
  previous: PostureSession,
  status: PostureStatus,
  deltaSeconds: number,
  canAdvance = true,
  timestampMs = 0
): PostureSession {
  const nextHoldSeconds = status === "correct" && canAdvance
    ? previous.holdSeconds + Math.max(0, deltaSeconds)
    : previous.holdSeconds;
  return {
    ...previous,
    holdSeconds: nextHoldSeconds,
    bestHoldSeconds: Math.max(previous.bestHoldSeconds, nextHoldSeconds),
    status,
    lastValidAt: status === "correct" && canAdvance ? timestampMs : previous.lastValidAt
  };
}

export function calculateAngles(landmarks: PoseLandmarks): Record<string, number> {
  return {
    left_knee: angleAt(landmarks.left_hip, landmarks.left_knee, landmarks.left_ankle),
    right_knee: angleAt(landmarks.right_hip, landmarks.right_knee, landmarks.right_ankle),
    left_hip: angleAt(landmarks.left_shoulder, landmarks.left_hip, landmarks.left_knee),
    right_hip: angleAt(landmarks.right_shoulder, landmarks.right_hip, landmarks.right_knee),
    left_elbow: angleAt(landmarks.left_shoulder, landmarks.left_elbow, landmarks.left_wrist),
    right_elbow: angleAt(landmarks.right_shoulder, landmarks.right_elbow, landmarks.right_wrist),
    torso_line: lineAngle(landmarks.left_shoulder, landmarks.left_hip),
    plank_line: lineAngle(landmarks.left_shoulder, landmarks.left_ankle)
  };
}

function scoreExercise(exerciseId: ExerciseId, landmarks: PoseLandmarks, angles: Record<string, number>) {
  if (exerciseId === "squat") {
    const knee = average(angles.left_knee, angles.right_knee);
    const hip = average(angles.left_hip, angles.right_hip);
    const standingScore = 100 - Math.abs(knee - 170) * 0.85 - Math.abs(hip - 170) * 0.35;
    const bottomScore = 100 - Math.abs(knee - 95) * 1.05 - Math.abs(hip - 90) * 0.5;
    return clampScore(Math.max(standingScore, bottomScore));
  }
  if (exerciseId === "curl_biceps") {
    const elbow = average(angles.left_elbow, angles.right_elbow);
    const shoulderDrift = Math.abs((landmarks.left_elbow?.x || 0.42) - (landmarks.left_shoulder?.x || 0.42)) * 160;
    return clampScore(100 - Math.min(Math.abs(elbow - 60), Math.abs(elbow - 165)) * 0.28 - shoulderDrift);
  }
  if (exerciseId === "push_up") {
    const elbow = average(angles.left_elbow, angles.right_elbow);
    const shoulder = landmarks.left_shoulder;
    const hip = landmarks.left_hip;
    const ankle = landmarks.left_ankle;
    const hipOffset = shoulder && hip && ankle ? pointLineDistance(hip, shoulder, ankle) : 0.25;
    const highScore = 100 - Math.abs(elbow - 165) * 0.5 - hipOffset * 280;
    const lowScore = 100 - Math.abs(elbow - 85) * 0.7 - hipOffset * 280;
    return clampScore(Math.max(highScore, lowScore));
  }
  if (exerciseId === "wall_sit") {
    const metrics = wallSitMetrics(landmarks, angles);
    const kneePenalty = Math.abs(metrics.knee - 95) * 1.05;
    const hipPenalty = Math.abs(metrics.hip - 95) * 0.45;
    const torsoPenalty = Math.max(0, metrics.torsoDeviation - 10) * 1.25;
    const shinPenalty = Math.max(0, metrics.shinDeviation - 12) * 0.85;
    const symmetryPenalty = metrics.symmetry * 0.55;
    return clampScore(100 - kneePenalty - hipPenalty - torsoPenalty - shinPenalty - symmetryPenalty);
  }
  if (exerciseId === "tree_pose") {
    const metrics = treePoseMetrics(landmarks, angles);
    const supportPenalty = Math.abs(metrics.supportKnee - 172) * 0.75;
    const bentPenalty = Math.max(0, metrics.bentKnee - 125) * 0.9 + Math.max(0, 55 - metrics.bentKnee) * 0.9;
    const torsoPenalty = Math.max(0, metrics.torsoDeviation - 10) * 1.2;
    const balancePenalty = metrics.supportFootDrift * 260;
    const footPenalty = Math.max(0, metrics.foldedFootDistance - 0.18) * 190;
    const armsPenalty = metrics.armsMissing ? 6 : metrics.armsRaised ? 0 : 28;
    const handsCenterPenalty = metrics.handsCentered ? 0 : 10;
    return clampScore(100 - supportPenalty - bentPenalty - torsoPenalty - balancePenalty - footPenalty - armsPenalty - handsCenterPenalty);
  }
  const shoulder = landmarks.left_shoulder;
  const hip = landmarks.left_hip;
  const ankle = landmarks.left_ankle;
  if (!shoulder || !hip || !ankle) return 0;
  const hipOffset = pointLineDistance(hip, shoulder, ankle);
  return clampScore(100 - hipOffset * 360 - Math.abs((shoulder.y || 0) - (ankle.y || 0)) * 30);
}

function detectErrors(exerciseId: ExerciseId, landmarks: PoseLandmarks, angles: Record<string, number>, status: PostureStatus) {
  const errors: string[] = [];
  if (exerciseId === "tree_pose") {
    const metrics = treePoseMetrics(landmarks, angles);
    if (metrics.armsMissing) errors.push("Mains non detectees, score bras partiel");
    if (!metrics.armsMissing && !metrics.wristsAboveShoulders) errors.push("Levez les bras au-dessus de la tete");
    if (!metrics.armsMissing && !metrics.handsCentered) errors.push("Gardez les mains alignees au-dessus du buste");
    if (status !== "correct") {
      if (metrics.torsoDeviation > 22) errors.push("Redresse le buste");
      if (Math.abs(metrics.supportKnee - 172) > 22 || metrics.supportFootDrift > 0.08) errors.push("Stabilise la jambe d'appui");
      if (metrics.bentKnee > 130 || metrics.foldedFootDistance > 0.2) errors.push("Ouvre davantage le genou");
    }
    return errors.slice(0, 3);
  }
  if (status === "correct") return [];
  if (exerciseId === "squat") {
    const knee = average(angles.left_knee, angles.right_knee);
    if (knee > 145) errors.push("descente trop courte");
    if (knee < 70) errors.push("genoux trop fermes");
    if (average(angles.left_hip, angles.right_hip) < 55) errors.push("buste trop penche");
  } else if (exerciseId === "curl_biceps") {
    const elbow = average(angles.left_elbow, angles.right_elbow);
    if (elbow > 120) errors.push("flexion du coude insuffisante");
    if (Math.abs((landmarks.left_elbow?.x || 0.42) - (landmarks.left_shoulder?.x || 0.42)) > 0.08) errors.push("coude trop mobile");
  } else if (exerciseId === "push_up") {
    const elbow = average(angles.left_elbow, angles.right_elbow);
    if (elbow > 120) errors.push("descente trop courte");
    const shoulder = landmarks.left_shoulder;
    const hip = landmarks.left_hip;
    const ankle = landmarks.left_ankle;
    if (shoulder && hip && ankle && pointLineDistance(hip, shoulder, ankle) > 0.08) errors.push("hanches hors alignement");
  } else if (exerciseId === "wall_sit") {
    const metrics = wallSitMetrics(landmarks, angles);
    if (metrics.knee > 120) errors.push("Descends un peu plus");
    if (metrics.knee > 135) errors.push("Plie davantage les genoux");
    if (metrics.knee < 75) errors.push("Remonte legerement");
    if (metrics.torsoDeviation > 25) errors.push("Garde le buste droit");
    if (metrics.symmetry > 28) errors.push("Equilibre mieux gauche et droite");
    if (metrics.shinDeviation > 32) errors.push("Stabilise les jambes");
  } else {
    const shoulder = landmarks.left_shoulder;
    const hip = landmarks.left_hip;
    const ankle = landmarks.left_ankle;
    if (shoulder && hip && ankle && pointLineDistance(hip, shoulder, ankle) > 0.08) {
      errors.push("hanches hors alignement");
    }
  }
  return errors.slice(0, 3);
}

function observedMovementPhase(exerciseId: ExerciseId, landmarks: PoseLandmarks, angles: Record<string, number>): ObservedMovementPhase {
  if (exerciseId === "squat") {
    const knee = average(angles.left_knee, angles.right_knee);
    if (knee > 150) return "phase_initiale";
    if (knee < 115) return "phase_contractee";
    return "phase_transition";
  }
  if (exerciseId === "curl_biceps") {
    const elbow = average(angles.left_elbow, angles.right_elbow);
    if (elbow > 145) return "phase_initiale";
    if (elbow < 65) return "phase_contractee";
    return "phase_transition";
  }
  if (exerciseId === "push_up") {
    const elbow = average(angles.left_elbow, angles.right_elbow);
    if (elbow > 145) return "phase_initiale";
    if (elbow < 95) return "phase_contractee";
    return "phase_transition";
  }
  return "phase_initiale";
}

function requiredMissingLandmarks(exercise: ExerciseConfig, landmarks: PoseLandmarks): PoseLandmarkName[] {
  return exercise.requiredLandmarks.filter((landmark) => !landmarks[landmark]);
}

function missingLandmarksError(missingLandmarks: PoseLandmarkName[]) {
  if (!missingLandmarks.length) return [];
  return [`points cles manquants: ${missingLandmarks.map(formatLandmarkName).join(", ")}`];
}

function formatLandmarkName(landmark: PoseLandmarkName) {
  return landmark.replaceAll("_", " ");
}

function statusFromScore(score: number, exercise: ExerciseConfig): PostureStatus {
  if (score >= exercise.correctThreshold) return "correct";
  if (score >= exercise.almostThreshold) return "almost";
  return "incorrect";
}

function angleAt(a?: PosePoint, b?: PosePoint, c?: PosePoint) {
  if (!a || !b || !c) return 0;
  const ab = { x: a.x - b.x, y: a.y - b.y };
  const cb = { x: c.x - b.x, y: c.y - b.y };
  const dot = ab.x * cb.x + ab.y * cb.y;
  const magnitude = Math.hypot(ab.x, ab.y) * Math.hypot(cb.x, cb.y);
  if (!magnitude) return 0;
  return Math.round((Math.acos(Math.max(-1, Math.min(1, dot / magnitude))) * 180) / Math.PI);
}

function lineAngle(a?: PosePoint, b?: PosePoint) {
  if (!a || !b) return 0;
  return Math.round((Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI);
}

function average(a = 0, b = 0) {
  return (a + b) / 2;
}

function distance(a?: PosePoint, b?: PosePoint) {
  if (!a || !b) return 0;
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function pointLineDistance(point: PosePoint, lineStart: PosePoint, lineEnd: PosePoint) {
  const numerator = Math.abs(
    (lineEnd.y - lineStart.y) * point.x -
    (lineEnd.x - lineStart.x) * point.y +
    lineEnd.x * lineStart.y -
    lineEnd.y * lineStart.x
  );
  const denominator = Math.hypot(lineEnd.y - lineStart.y, lineEnd.x - lineStart.x);
  return denominator ? numerator / denominator : 0;
}

function wallSitMetrics(landmarks: PoseLandmarks, angles: Record<string, number>) {
  const leftTorso = lineAngle(landmarks.left_shoulder, landmarks.left_hip);
  const rightTorso = lineAngle(landmarks.right_shoulder, landmarks.right_hip);
  const leftShin = lineAngle(landmarks.left_knee, landmarks.left_ankle);
  const rightShin = lineAngle(landmarks.right_knee, landmarks.right_ankle);
  return {
    knee: average(angles.left_knee, angles.right_knee),
    hip: average(angles.left_hip, angles.right_hip),
    torsoDeviation: average(verticalDeviation(leftTorso), verticalDeviation(rightTorso)),
    shinDeviation: average(verticalDeviation(leftShin), verticalDeviation(rightShin)),
    symmetry: Math.abs(angles.left_knee - angles.right_knee) + Math.abs(angles.left_hip - angles.right_hip) * 0.5
  };
}

function treePoseMetrics(landmarks: PoseLandmarks, angles: Record<string, number>) {
  const leftIsSupport = angles.left_knee >= angles.right_knee;
  const supportHip = leftIsSupport ? landmarks.left_hip : landmarks.right_hip;
  const supportKnee = leftIsSupport ? landmarks.left_knee : landmarks.right_knee;
  const supportAnkle = leftIsSupport ? landmarks.left_ankle : landmarks.right_ankle;
  const foldedAnkle = leftIsSupport ? landmarks.right_ankle : landmarks.left_ankle;
  const foldedKnee = leftIsSupport ? landmarks.right_knee : landmarks.left_knee;
  const leftTorso = lineAngle(landmarks.left_shoulder, landmarks.left_hip);
  const rightTorso = lineAngle(landmarks.right_shoulder, landmarks.right_hip);
  const leftWrist = landmarks.left_wrist;
  const rightWrist = landmarks.right_wrist;
  const leftElbow = landmarks.left_elbow;
  const rightElbow = landmarks.right_elbow;
  const leftShoulder = landmarks.left_shoulder;
  const rightShoulder = landmarks.right_shoulder;
  const armsVisible = Boolean(leftWrist && rightWrist && leftShoulder && rightShoulder);
  const elbowsVisible = Boolean(leftElbow && rightElbow && leftShoulder && rightShoulder);
  const wristsAboveShoulders = armsVisible && leftWrist!.y < leftShoulder!.y - 0.08 && rightWrist!.y < rightShoulder!.y - 0.08;
  const elbowsHigh = !elbowsVisible || (leftElbow!.y < leftShoulder!.y + 0.02 && rightElbow!.y < rightShoulder!.y + 0.02);
  const shoulderCenter = leftShoulder && rightShoulder ? average(leftShoulder.x, rightShoulder.x) : 0.5;
  const wristCenter = leftWrist && rightWrist ? average(leftWrist.x, rightWrist.x) : shoulderCenter;
  const handsCentered = !armsVisible || Math.abs(wristCenter - shoulderCenter) < 0.18;
  const armsRaised = Boolean(wristsAboveShoulders && elbowsHigh);
  return {
    supportKnee: leftIsSupport ? angles.left_knee : angles.right_knee,
    bentKnee: leftIsSupport ? angles.right_knee : angles.left_knee,
    torsoDeviation: average(verticalDeviation(leftTorso), verticalDeviation(rightTorso)),
    supportFootDrift: supportHip && supportAnkle ? Math.abs(supportHip.x - supportAnkle.x) : 0.2,
    foldedFootDistance: Math.min(distance(foldedAnkle, supportKnee), distance(foldedAnkle, supportHip), distance(foldedAnkle, foldedKnee) * 0.8),
    armsMissing: !armsVisible,
    armsVisible,
    wristsAboveShoulders,
    handsCentered,
    armsRaised
  };
}

function verticalDeviation(angle: number) {
  return Math.abs(90 - Math.abs(angle));
}

function clampScore(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}
