import assert from "node:assert/strict";
import { test } from "node:test";
import { COACH_EXERCISES } from "./exercises";
import {
  advanceDynamicSession,
  advanceStaticSession,
  createInitialExerciseSessions,
  createInitialPostureSession,
  evaluatePosture,
  validateStaticHold
} from "./logic";
import { detectHandGestureForTest } from "./pose-engine";
import type { PoseLandmarks, PostureSession } from "./types";

test("biceps curl counts one rep after low high low", () => {
  const exercise = COACH_EXERCISES.curl_biceps;
  let session = createInitialPostureSession();

  session = evaluatePosture(exercise, curlPose("low"), session, 0.1, 1000).session;
  session = evaluatePosture(exercise, curlPose("high"), session, 0.1, 1700).session;
  session = evaluatePosture(exercise, curlPose("low"), session, 0.1, 2400).session;

  assert.equal(session.reps, 1);
  assert.equal(session.repsInCurrentSet, 1);
  assert.equal(session.sets, 0);
});

test("dynamic counter ignores duplicate completion during cooldown", () => {
  let session: PostureSession = {
    ...createInitialPostureSession(),
    phase: "phase_contractee"
  };

  session = advanceDynamicSession(session, "phase_initiale", "correct", 12, 1000);
  session = advanceDynamicSession({ ...session, phase: "phase_contractee" }, "phase_initiale", "correct", 12, 1300);

  assert.equal(session.reps, 1);
  assert.equal(session.repsInCurrentSet, 1);
});

test("dynamic counter completes a set at target reps", () => {
  let session = createInitialPostureSession();

  session = advanceDynamicSession(session, "phase_contractee", "correct", 2, 1000);
  session = advanceDynamicSession(session, "phase_initiale", "correct", 2, 1700);
  session = advanceDynamicSession(session, "phase_contractee", "correct", 2, 2400);
  session = advanceDynamicSession(session, "phase_initiale", "correct", 2, 3100);

  assert.equal(session.reps, 2);
  assert.equal(session.repsInCurrentSet, 0);
  assert.equal(session.sets, 1);
});

test("push up counts one rep after high low high", () => {
  const exercise = COACH_EXERCISES.push_up;
  let session = createInitialPostureSession();

  session = evaluatePosture(exercise, pushUpPose("high"), session, 0.1, 1000).session;
  session = evaluatePosture(exercise, pushUpPose("low"), session, 0.1, 1700).session;
  session = evaluatePosture(exercise, pushUpPose("high"), session, 0.1, 2400).session;

  assert.equal(session.reps, 1);
  assert.equal(session.repsInCurrentSet, 1);
});

test("static hold advances only when posture status is correct", () => {
  let session = createInitialPostureSession();

  session = advanceStaticSession(session, "correct", 2.5, true, 1000);
  session = advanceStaticSession(session, "almost", 4, true, 5000);
  session = advanceStaticSession(session, "incorrect", 4, true, 9000);

  assert.equal(session.holdSeconds, 2.5);
  assert.equal(session.bestHoldSeconds, 2.5);
});

test("static hold pauses when required landmarks are missing", () => {
  const exercise = COACH_EXERCISES.gainage;
  let session = createInitialPostureSession();

  session = evaluatePosture(exercise, exercise.guide, session, 3, 1000).session;
  session = evaluatePosture(exercise, { left_shoulder: exercise.guide.left_shoulder }, session, 3, 4000).session;

  assert.equal(session.holdSeconds, 3);
});

test("wall sit hold advances as a static exercise", () => {
  const exercise = COACH_EXERCISES.wall_sit;
  let session = createInitialPostureSession();

  session = evaluatePosture(exercise, exercise.guide, session, 4, 1000).session;
  session = evaluatePosture(exercise, { left_knee: exercise.guide.left_knee }, session, 4, 5000).session;

  assert.equal(session.holdSeconds, 4);
});

test("wall sit reports explicit correction when knees are too open", () => {
  const exercise = COACH_EXERCISES.wall_sit;
  const evaluation = evaluatePosture(exercise, wallSitPose("too_high"), createInitialPostureSession(), 1, 1000);

  assert.equal(evaluation.status, "incorrect");
  assert.ok(evaluation.detectedErrors.includes("Descends un peu plus"));
});

test("tree pose hold advances when balance is correct", () => {
  const exercise = COACH_EXERCISES.tree_pose;
  const evaluation = evaluatePosture(exercise, exercise.guide, createInitialPostureSession(), 3, 1000);

  assert.equal(evaluation.status, "correct");
  assert.equal(evaluation.session.holdSeconds, 3);
});

test("tree pose reports balance correction when support leg is unstable", () => {
  const exercise = COACH_EXERCISES.tree_pose;
  const evaluation = evaluatePosture(exercise, unstableTreePose(), createInitialPostureSession(), 1, 1000);

  assert.notEqual(evaluation.status, "correct");
  assert.ok(evaluation.detectedErrors.includes("Stabilise la jambe d'appui"));
});

test("tree pose scores lower and asks for arms when hands are visible but down", () => {
  const exercise = COACH_EXERCISES.tree_pose;
  const raised = evaluatePosture(exercise, exercise.guide, createInitialPostureSession(), 1, 1000);
  const armsDown = evaluatePosture(exercise, treePoseArmsDown(), createInitialPostureSession(), 1, 1000);

  assert.ok(raised.score > armsDown.score);
  assert.ok(armsDown.detectedErrors.includes("Levez les bras au-dessus de la tete"));
});

test("tree pose keeps partial score when hands are not visible", () => {
  const exercise = COACH_EXERCISES.tree_pose;
  const { left_wrist: _leftWrist, right_wrist: _rightWrist, ...withoutHands } = exercise.guide;
  const evaluation = evaluatePosture(exercise, withoutHands, createInitialPostureSession(), 1, 1000);

  assert.ok(evaluation.score > 0);
  assert.ok(evaluation.detectedErrors.includes("Mains non detectees, score bras partiel"));
});

test("static hold does not advance while session is paused", () => {
  let session = createInitialPostureSession();

  session = advanceStaticSession(session, "correct", 2, true, 1000);
  session = advanceStaticSession(session, "correct", 5, false, 6000);

  assert.equal(session.holdSeconds, 2);
});

test("validating a static hold resets current series and keeps best time", () => {
  const session = validateStaticHold({
    ...createInitialPostureSession(),
    holdSeconds: 18,
    bestHoldSeconds: 25,
    validatedHolds: [25],
    sets: 1,
    repsInCurrentSet: 3,
    phase: "phase_contractee",
    status: "correct",
    lastRepAt: 1200,
    lastValidAt: 1200
  });

  assert.equal(session.holdSeconds, 0);
  assert.equal(session.bestHoldSeconds, 25);
  assert.deepEqual(session.validatedHolds, [25, 18]);
  assert.equal(session.sets, 2);
  assert.equal(session.repsInCurrentSet, 0);
  assert.equal(session.phase, "phase_initiale");
  assert.equal(session.status, "incorrect");
  assert.equal(session.lastValidAt, null);
});

test("exercise sessions keep state independently when switching exercise", () => {
  const sessions = createInitialExerciseSessions();
  const squatSession = advanceDynamicSession(
    { ...sessions.squat, phase: "phase_contractee" },
    "phase_initiale",
    "correct",
    COACH_EXERCISES.squat.targetRepsPerSet,
    1000
  );
  const nextSessions = { ...sessions, squat: squatSession };

  assert.equal(nextSessions.squat.reps, 1);
  assert.equal(nextSessions.curl_biceps.reps, 0);
  assert.equal(nextSessions.squat.reps, 1);
});

test("hand OK gesture is recognized", () => {
  assert.equal(detectHandGestureForTest(okHand()), "ok");
});

test("OK gesture keeps priority when thumb and index are closed", () => {
  assert.equal(detectHandGestureForTest(okHand()), "ok");
});

test("I love you pause gesture is recognized for pause and resume", () => {
  assert.equal(detectHandGestureForTest(pauseHand()), "pause");
});

test("pause gesture is rejected when middle finger is raised too", () => {
  assert.notEqual(detectHandGestureForTest(pauseHandWithMiddleRaised()), "pause");
});

test("peace gesture is recognized for photo capture", () => {
  assert.equal(detectHandGestureForTest(peaceHand()), "peace");
});

test("peace gesture is not blocked by a non-pause thumb position", () => {
  assert.equal(detectHandGestureForTest(peaceWithOpenThumbHand()), "peace");
});

test("thumbs up no longer triggers a photo gesture", () => {
  assert.equal(detectHandGestureForTest(thumbsUpHand()), null);
});

test("gesture detection works from hand landmarks without body pose", () => {
  assert.equal(detectHandGestureForTest(pauseHand()), "pause");
});

test("missing hand landmarks return no gesture", () => {
  assert.equal(detectHandGestureForTest(emptyHand()), null);
});

function curlPose(phase: "low" | "high"): PoseLandmarks {
  const wristY = phase === "low" ? 0.75 : 0.36;
  const wristOffset = phase === "low" ? 0 : 0.12;
  return {
    left_shoulder: { x: 0.42, y: 0.3 },
    right_shoulder: { x: 0.58, y: 0.3 },
    left_elbow: { x: 0.42, y: 0.5 },
    right_elbow: { x: 0.58, y: 0.5 },
    left_wrist: { x: 0.42 + wristOffset, y: wristY },
    right_wrist: { x: 0.58 - wristOffset, y: wristY }
  };
}

function pushUpPose(phase: "low" | "high"): PoseLandmarks {
  const low = phase === "low";
  return {
    left_shoulder: { x: low ? 0.28 : 0.26, y: low ? 0.68 : 0.5 },
    right_shoulder: { x: low ? 0.28 : 0.26, y: low ? 0.72 : 0.54 },
    left_elbow: { x: 0.2, y: 0.62 },
    right_elbow: { x: 0.2, y: 0.66 },
    left_wrist: { x: 0.16, y: 0.74 },
    right_wrist: { x: 0.16, y: 0.76 },
    left_hip: { x: 0.5, y: low ? 0.66 : 0.54 },
    right_hip: { x: 0.5, y: low ? 0.7 : 0.58 },
    left_ankle: { x: 0.84, y: 0.65 },
    right_ankle: { x: 0.84, y: 0.69 }
  };
}

function wallSitPose(phase: "too_high"): PoseLandmarks {
  const kneeX = phase === "too_high" ? 0.5 : 0.6;
  return {
    left_shoulder: { x: 0.4, y: 0.34 },
    right_shoulder: { x: 0.48, y: 0.34 },
    left_hip: { x: 0.4, y: 0.62 },
    right_hip: { x: 0.48, y: 0.62 },
    left_knee: { x: kneeX, y: 0.72 },
    right_knee: { x: kneeX + 0.08, y: 0.72 },
    left_ankle: { x: 0.6, y: 0.86 },
    right_ankle: { x: 0.68, y: 0.86 }
  };
}

function unstableTreePose(): PoseLandmarks {
  const guide = COACH_EXERCISES.tree_pose.guide;
  return {
    ...guide,
    left_ankle: { x: 0.64, y: guide.left_ankle?.y || 0.9 }
  };
}

function treePoseArmsDown(): PoseLandmarks {
  const guide = COACH_EXERCISES.tree_pose.guide;
  return {
    ...guide,
    left_elbow: { x: 0.39, y: 0.42 },
    right_elbow: { x: 0.61, y: 0.42 },
    left_wrist: { x: 0.42, y: 0.58 },
    right_wrist: { x: 0.58, y: 0.58 }
  };
}

function emptyHand() {
  return Array.from({ length: 21 }, () => ({ x: 0.5, y: 0.7 }));
}

function okHand() {
  const hand = emptyHand();
  hand[0] = { x: 0.5, y: 0.82 };
  hand[1] = { x: 0.47, y: 0.74 };
  hand[2] = { x: 0.45, y: 0.64 };
  hand[3] = { x: 0.43, y: 0.55 };
  hand[4] = { x: 0.43, y: 0.48 };
  hand[5] = { x: 0.44, y: 0.66 };
  hand[6] = { x: 0.44, y: 0.56 };
  hand[8] = { x: 0.445, y: 0.49 };
  hand[9] = { x: 0.5, y: 0.66 };
  hand[10] = { x: 0.5, y: 0.56 };
  hand[12] = { x: 0.5, y: 0.34 };
  hand[13] = { x: 0.56, y: 0.66 };
  hand[14] = { x: 0.56, y: 0.57 };
  hand[16] = { x: 0.6, y: 0.38 };
  hand[17] = { x: 0.62, y: 0.66 };
  hand[18] = { x: 0.62, y: 0.6 };
  hand[20] = { x: 0.68, y: 0.45 };
  return hand;
}

function pauseHand() {
  const hand = emptyHand();
  hand[0] = { x: 0.5, y: 0.82 };
  hand[1] = { x: 0.49, y: 0.74 };
  hand[2] = { x: 0.45, y: 0.72 };
  hand[3] = { x: 0.36, y: 0.72 };
  hand[4] = { x: 0.25, y: 0.72 };
  hand[5] = { x: 0.46, y: 0.66 };
  hand[6] = { x: 0.46, y: 0.55 };
  hand[8] = { x: 0.43, y: 0.33 };
  hand[9] = { x: 0.55, y: 0.66 };
  hand[10] = { x: 0.55, y: 0.58 };
  hand[12] = { x: 0.55, y: 0.69 };
  hand[13] = { x: 0.6, y: 0.66 };
  hand[14] = { x: 0.6, y: 0.58 };
  hand[16] = { x: 0.6, y: 0.7 };
  hand[17] = { x: 0.64, y: 0.68 };
  hand[18] = { x: 0.66, y: 0.58 };
  hand[20] = { x: 0.72, y: 0.38 };
  return hand;
}

function pauseHandWithMiddleRaised() {
  const hand = pauseHand();
  hand[10] = { x: 0.55, y: 0.55 };
  hand[12] = { x: 0.58, y: 0.34 };
  return hand;
}

function peaceHand() {
  const hand = emptyHand();
  hand[0] = { x: 0.5, y: 0.82 };
  hand[1] = { x: 0.5, y: 0.72 };
  hand[2] = { x: 0.49, y: 0.7 };
  hand[3] = { x: 0.48, y: 0.68 };
  hand[4] = { x: 0.47, y: 0.66 };
  hand[5] = { x: 0.45, y: 0.66 };
  hand[6] = { x: 0.45, y: 0.55 };
  hand[8] = { x: 0.42, y: 0.34 };
  hand[9] = { x: 0.52, y: 0.66 };
  hand[10] = { x: 0.52, y: 0.55 };
  hand[12] = { x: 0.56, y: 0.34 };
  hand[13] = { x: 0.58, y: 0.66 };
  hand[14] = { x: 0.58, y: 0.58 };
  hand[16] = { x: 0.58, y: 0.68 };
  hand[17] = { x: 0.63, y: 0.68 };
  hand[18] = { x: 0.63, y: 0.6 };
  hand[20] = { x: 0.63, y: 0.7 };
  return hand;
}

function peaceWithOpenThumbHand() {
  const hand = peaceHand();
  hand[1] = { x: 0.48, y: 0.74 };
  hand[2] = { x: 0.42, y: 0.72 };
  hand[3] = { x: 0.33, y: 0.66 };
  hand[4] = { x: 0.24, y: 0.6 };
  return hand;
}

function thumbsUpHand() {
  const hand = emptyHand();
  hand[0] = { x: 0.5, y: 0.82 };
  hand[3] = { x: 0.5, y: 0.62 };
  hand[4] = { x: 0.5, y: 0.42 };
  hand[6] = { x: 0.45, y: 0.58 };
  hand[8] = { x: 0.45, y: 0.67 };
  hand[9] = { x: 0.5, y: 0.66 };
  hand[10] = { x: 0.5, y: 0.56 };
  hand[12] = { x: 0.5, y: 0.66 };
  hand[14] = { x: 0.55, y: 0.58 };
  hand[16] = { x: 0.55, y: 0.68 };
  hand[18] = { x: 0.6, y: 0.6 };
  hand[20] = { x: 0.6, y: 0.7 };
  return hand;
}
