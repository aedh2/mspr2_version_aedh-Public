import type {
  HandLandmarker as MediaPipeHandLandmarker,
  HandLandmarkerResult as MediaPipeHandLandmarkerResult,
  NormalizedLandmark,
  PoseLandmarker as MediaPipePoseLandmarker,
  PoseLandmarkerResult as MediaPipePoseLandmarkerResult
} from "@mediapipe/tasks-vision";
import type { ExerciseId, HandDetection, HandLandmarks, PoseLandmarkName, PoseLandmarks, PosePoint } from "./types";

type MediaPipeLandmark = NormalizedLandmark;
const MIN_LANDMARK_VISIBILITY = 0.35;
const MIN_VISIBLE_CORE_POINTS = 4;
const SMOOTHING_FACTOR = 0.32;
const HAND_SMOOTHING_FACTOR = 0.85;
const HAND_SMOOTHING_RESET_DISTANCE = 0.08;

type PoseDetectorMode = "mediapipe" | "simulation";

export type PoseDetector = {
  mode: PoseDetectorMode;
  setupError?: string;
  estimate: (video: HTMLVideoElement | null, exerciseId: ExerciseId, timestamp: number) => Promise<PoseLandmarks | null>;
  detectOkGesture?: (video: HTMLVideoElement | null, timestamp: number) => Promise<boolean>;
  detectHand?: (video: HTMLVideoElement | null, timestamp: number) => Promise<HandDetection>;
  dispose: () => void;
};

export async function createPoseDetector(): Promise<PoseDetector> {
  try {
    return await MediaPipePoseDetector.create();
  } catch (error) {
    return new SimulationPoseDetector(formatMediaPipeError(error));
  }
}

export function createSimulationPoseDetector(reason = "Mode simulation active.") {
  return new SimulationPoseDetector(reason);
}

class MediaPipePoseDetector implements PoseDetector {
  mode: PoseDetectorMode = "mediapipe";
  private previousLandmarks: PoseLandmarks | null = null;
  private previousHands: HandLandmarks[] = [];

  private constructor(
    private readonly landmarker: MediaPipePoseLandmarker,
    private readonly handLandmarker?: MediaPipeHandLandmarker
  ) {}

  static async create() {
    const visionModule = await import("@mediapipe/tasks-vision");
    const wasmBaseUrl = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm";
    const modelAssetPath = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";
    const handModelAssetPath = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";
    const vision = await visionModule.FilesetResolver.forVisionTasks(wasmBaseUrl);

    let landmarker: MediaPipePoseLandmarker;
    try {
      landmarker = await visionModule.PoseLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath, delegate: "GPU" },
        runningMode: "VIDEO",
        numPoses: 1,
        minPoseDetectionConfidence: 0.5,
        minPosePresenceConfidence: 0.5,
        minTrackingConfidence: 0.5
      });
    } catch {
      landmarker = await visionModule.PoseLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath, delegate: "CPU" },
        runningMode: "VIDEO",
        numPoses: 1,
        minPoseDetectionConfidence: 0.5,
        minPosePresenceConfidence: 0.5,
        minTrackingConfidence: 0.5
      });
    }

    let handLandmarker: MediaPipeHandLandmarker | undefined;
    try {
      handLandmarker = await visionModule.HandLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: handModelAssetPath, delegate: "GPU" },
        runningMode: "VIDEO",
        numHands: 2,
        minHandDetectionConfidence: 0.55,
        minHandPresenceConfidence: 0.55,
        minTrackingConfidence: 0.55
      });
    } catch {
      try {
        handLandmarker = await visionModule.HandLandmarker.createFromOptions(vision, {
          baseOptions: { modelAssetPath: handModelAssetPath, delegate: "CPU" },
          runningMode: "VIDEO",
          numHands: 2,
          minHandDetectionConfidence: 0.55,
          minHandPresenceConfidence: 0.55,
          minTrackingConfidence: 0.55
        });
      } catch {
        handLandmarker = undefined;
      }
    }

    return new MediaPipePoseDetector(landmarker, handLandmarker);
  }

  async estimate(video: HTMLVideoElement | null, _exerciseId: ExerciseId, timestamp: number): Promise<PoseLandmarks | null> {
    if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || !video.videoWidth || !video.videoHeight) {
      return null;
    }

    const result = this.detect(video, timestamp);
    const landmarks = result.landmarks?.[0];
    if (!landmarks) {
      return null;
    }
    const mapped = mapMediaPipeLandmarks(landmarks);
    if (!mapped) {
      return null;
    }
    this.previousLandmarks = smoothPose(this.previousLandmarks, mapped);
    return this.previousLandmarks;
  }

  dispose() {
    this.landmarker.close?.();
    this.handLandmarker?.close?.();
  }

  async detectOkGesture(video: HTMLVideoElement | null, timestamp: number): Promise<boolean> {
    const hand = await this.detectHand(video, timestamp);
    return hand.gesture === "ok";
  }

  async detectHand(video: HTMLVideoElement | null, timestamp: number): Promise<HandDetection> {
    if (!this.handLandmarker || !video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || !video.videoWidth || !video.videoHeight) {
      this.previousHands = [];
      return emptyHandDetection();
    }
    try {
      const result = this.handLandmarker.detectForVideo(video, timestamp);
      const mappedHands = (result.landmarks || []).map(mapHandLandmarks).filter((hand) => hand.length >= 21);
      this.previousHands = smoothHands(this.previousHands, mappedHands);
      return {
        landmarks: this.previousHands,
        gesture: detectGesture(result)
      };
    } catch {
      this.previousHands = [];
      return emptyHandDetection();
    }
  }

  private detect(video: HTMLVideoElement, timestamp: number): MediaPipePoseLandmarkerResult {
    return this.landmarker.detectForVideo(video, timestamp);
  }
}

class SimulationPoseDetector implements PoseDetector {
  mode: PoseDetectorMode = "simulation";

  constructor(readonly setupError?: string) {}

  async estimate(video: HTMLVideoElement | null, exerciseId: ExerciseId, timestamp: number): Promise<PoseLandmarks | null> {
    if (video && video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      return null;
    }
    const t = timestamp / 1000;
    if (exerciseId === "squat") return squatPose(t);
    if (exerciseId === "curl_biceps") return curlPose(t);
    if (exerciseId === "push_up") return pushUpPose(t);
    if (exerciseId === "wall_sit") return wallSitPose(t);
    if (exerciseId === "tree_pose") return treePose(t);
    return plankPose(t);
  }

  async detectOkGesture() {
    return false;
  }

  async detectHand(): Promise<HandDetection> {
    return emptyHandDetection();
  }

  dispose() {
    return undefined;
  }
}

function emptyHandDetection(): HandDetection {
  return { landmarks: [], gesture: null };
}

function mapMediaPipeLandmarks(landmarks: MediaPipeLandmark[]): PoseLandmarks | null {
  const mapped: PoseLandmarks = {
    left_shoulder: toPoint(landmarks[11]),
    right_shoulder: toPoint(landmarks[12]),
    left_elbow: toPoint(landmarks[13]),
    right_elbow: toPoint(landmarks[14]),
    left_wrist: toPoint(landmarks[15]),
    right_wrist: toPoint(landmarks[16]),
    left_hip: toPoint(landmarks[23]),
    right_hip: toPoint(landmarks[24]),
    left_knee: toPoint(landmarks[25]),
    right_knee: toPoint(landmarks[26]),
    left_ankle: toPoint(landmarks[27]),
    right_ankle: toPoint(landmarks[28])
  };

  const visibleCorePoints = [
    mapped.left_shoulder,
    mapped.right_shoulder,
    mapped.left_hip,
    mapped.right_hip,
    mapped.left_knee,
    mapped.right_knee
  ].filter(Boolean).length;

  return visibleCorePoints >= MIN_VISIBLE_CORE_POINTS ? mapped : null;
}

function toPoint(landmark?: MediaPipeLandmark) {
  if (!landmark || landmark.x < -0.2 || landmark.x > 1.2 || landmark.y < -0.2 || landmark.y > 1.2) {
    return undefined;
  }
  if (landmark.visibility !== undefined && landmark.visibility < MIN_LANDMARK_VISIBILITY) {
    return undefined;
  }
  return {
    // The user-facing camera is mirrored in CSS, so mirror X for overlay alignment.
    x: clamp01(1 - landmark.x),
    y: clamp01(landmark.y),
    visibility: landmark.visibility
  };
}

function smoothPose(previous: PoseLandmarks | null, current: PoseLandmarks): PoseLandmarks {
  if (!previous) return current;
  const smoothed: PoseLandmarks = {};
  for (const [name, point] of Object.entries(current) as Array<[PoseLandmarkName, PoseLandmarks[PoseLandmarkName]]>) {
    if (!point) continue;
    const lastPoint = previous[name];
    smoothed[name] = lastPoint
      ? {
          x: lastPoint.x + (point.x - lastPoint.x) * SMOOTHING_FACTOR,
          y: lastPoint.y + (point.y - lastPoint.y) * SMOOTHING_FACTOR,
          visibility: point.visibility
        }
      : point;
  }
  return smoothed;
}

function mapHandLandmarks(landmarks: MediaPipeLandmark[]): HandLandmarks {
  return landmarks.map((landmark) => ({
    x: clamp01(1 - landmark.x),
    y: clamp01(landmark.y),
    visibility: landmark.visibility
  }));
}

function smoothHands(previous: HandLandmarks[], current: HandLandmarks[]): HandLandmarks[] {
  if (!current.length) return [];
  if (!previous.length) return current;
  return current.map((hand, handIndex) => {
    const previousHand = previous[handIndex];
    if (!previousHand) return hand;
    if (averageHandMotion(previousHand, hand) > HAND_SMOOTHING_RESET_DISTANCE) return hand;
    return hand.map((point, pointIndex) => smoothPoint(previousHand[pointIndex], point, HAND_SMOOTHING_FACTOR));
  });
}

function averageHandMotion(previous: HandLandmarks, current: HandLandmarks) {
  const count = Math.min(previous.length, current.length);
  if (!count) return Number.POSITIVE_INFINITY;
  let total = 0;
  for (let index = 0; index < count; index += 1) {
    total += Math.hypot(current[index].x - previous[index].x, current[index].y - previous[index].y);
  }
  return total / count;
}

function smoothPoint(previous: PosePoint | undefined, current: PosePoint, factor: number): PosePoint {
  if (!previous) return current;
  return {
    x: previous.x + (current.x - previous.x) * factor,
    y: previous.y + (current.y - previous.y) * factor,
    visibility: current.visibility
  };
}

function detectGesture(result: MediaPipeHandLandmarkerResult) {
  const hands = result.landmarks || [];
  if (hands.some(isOkHand)) return "ok";
  if (hands.some(isPauseHand)) return "pause";
  if (hands.some(isPeaceHand)) return "peace";
  return null;
}

export function detectHandGestureForTest(landmarks: Array<{ x: number; y: number; z?: number; visibility?: number }>) {
  if (isOkHand(landmarks as MediaPipeLandmark[])) return "ok";
  if (isPauseHand(landmarks as MediaPipeLandmark[])) return "pause";
  if (isPeaceHand(landmarks as MediaPipeLandmark[])) return "peace";
  return null;
}

type HandFinger = "index" | "middle" | "ring" | "pinky";

const FINGER_POINTS: Record<HandFinger, { mcp: number; pip: number; tip: number }> = {
  index: { mcp: 5, pip: 6, tip: 8 },
  middle: { mcp: 9, pip: 10, tip: 12 },
  ring: { mcp: 13, pip: 14, tip: 16 },
  pinky: { mcp: 17, pip: 18, tip: 20 }
};

function isOkHand(landmarks: MediaPipeLandmark[]) {
  if (!hasHandPoints(landmarks, [0, 4, 8, 9, 13, 17])) {
    return false;
  }
  const openFingers = ["middle", "ring", "pinky"].filter((finger) => isFingerExtended(landmarks, finger as HandFinger)).length;

  return isThumbCloseToIndex(landmarks) && openFingers >= 2;
}

function isPauseHand(landmarks: MediaPipeLandmark[]) {
  if (!hasHandPoints(landmarks, [0, 1, 2, 3, 4, 5, 8, 12, 16, 20])) {
    return false;
  }

  return (
    isThumbOpen(landmarks) &&
    isFingerExtended(landmarks, "index") &&
    isFingerExtended(landmarks, "pinky") &&
    isFingerFolded(landmarks, "middle") &&
    isFingerFolded(landmarks, "ring")
  );
}

function isPeaceHand(landmarks: MediaPipeLandmark[]) {
  const indexTip = landmarks[8];
  const middleTip = landmarks[12];
  if (!indexTip || !middleTip) {
    return false;
  }
  const scale = handScale(landmarks);
  const indexOpen = isFingerExtended(landmarks, "index");
  const middleOpen = isFingerExtended(landmarks, "middle");
  const ringFolded = isFingerFolded(landmarks, "ring");
  const pinkyFolded = isFingerFolded(landmarks, "pinky");
  const fingersSeparated = distance2d(indexTip, middleTip) > scale * 0.22;

  return indexOpen && middleOpen && ringFolded && pinkyFolded && fingersSeparated && !isPauseHand(landmarks);
}

function isFingerExtended(landmarks: MediaPipeLandmark[], finger: HandFinger) {
  const points = fingerPoints(landmarks, finger);
  const wrist = landmarks[0];
  if (!points || !wrist) return false;

  const scale = handScale(landmarks);
  const tipAbovePip = points.tip.y < points.pip.y - scale * 0.08;
  const tipAboveMcp = points.tip.y < points.mcp.y - scale * 0.12;
  const reachFromWrist = distance2d(wrist, points.tip) > Math.max(distance2d(wrist, points.pip), distance2d(wrist, points.mcp)) + scale * 0.1;

  return tipAbovePip && tipAboveMcp && reachFromWrist;
}

function isFingerFolded(landmarks: MediaPipeLandmark[], finger: HandFinger) {
  const points = fingerPoints(landmarks, finger);
  const wrist = landmarks[0];
  if (!points || !wrist) return false;

  const scale = handScale(landmarks);
  const tipNotAbovePip = points.tip.y >= points.pip.y - scale * 0.03;
  const tipNotClearlyAboveMcp = points.tip.y >= points.mcp.y - scale * 0.05;
  const shortReach = distance2d(wrist, points.tip) <= distance2d(wrist, points.pip) + scale * 0.08;

  return tipNotAbovePip || tipNotClearlyAboveMcp || shortReach;
}

function isThumbOpen(landmarks: MediaPipeLandmark[]) {
  const wrist = landmarks[0];
  const thumbCmc = landmarks[1];
  const thumbMcp = landmarks[2];
  const thumbIp = landmarks[3];
  const thumbTip = landmarks[4];
  const indexMcp = landmarks[5];
  if (!wrist || !thumbCmc || !thumbMcp || !thumbIp || !thumbTip || !indexMcp) return false;

  const scale = handScale(landmarks);
  const lateralSpread = Math.abs(thumbTip.x - thumbMcp.x) > scale * 0.45;
  const mostlyHorizontal = Math.abs(thumbTip.x - thumbMcp.x) > Math.abs(thumbTip.y - thumbMcp.y) * 0.7;
  const awayFromPalm = distance2d(thumbTip, indexMcp) > scale * 0.6;
  const extendedFromWrist = distance2d(wrist, thumbTip) > distance2d(wrist, thumbIp) + scale * 0.08;
  const extendedFromBase = distance2d(thumbCmc, thumbTip) > distance2d(thumbCmc, thumbIp) + scale * 0.08;

  return lateralSpread && mostlyHorizontal && awayFromPalm && extendedFromWrist && extendedFromBase;
}

function isThumbCloseToIndex(landmarks: MediaPipeLandmark[]) {
  const thumbTip = landmarks[4];
  const indexTip = landmarks[8];
  if (!thumbTip || !indexTip) return false;
  const scale = handScale(landmarks);
  return distance2d(thumbTip, indexTip) < scale * 0.45;
}

function fingerPoints(landmarks: MediaPipeLandmark[], finger: HandFinger) {
  const indexes = FINGER_POINTS[finger];
  const mcp = landmarks[indexes.mcp];
  const pip = landmarks[indexes.pip];
  const tip = landmarks[indexes.tip];
  if (!mcp || !pip || !tip) return null;
  return { mcp, pip, tip };
}

function handScale(landmarks: MediaPipeLandmark[]) {
  const wrist = landmarks[0];
  const middleMcp = landmarks[9];
  if (!wrist || !middleMcp) return 0.08;
  return Math.max(0.04, distance2d(wrist, middleMcp));
}

function hasHandPoints(landmarks: MediaPipeLandmark[], indexes: number[]) {
  return indexes.every((index) => Boolean(landmarks[index]));
}

function distance2d(a: MediaPipeLandmark, b: MediaPipeLandmark) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function clamp01(value: number) {
  return Math.max(0, Math.min(1, value));
}

function formatMediaPipeError(error: unknown) {
  if (error instanceof Error) {
    return `MediaPipe indisponible: ${error.message}`;
  }
  return "MediaPipe indisponible: mode simulation active.";
}

function squatPose(t: number): PoseLandmarks {
  const cycle = wave(t, 2.8);
  const squatDepth = cycle;
  const hipY = 0.42 + squatDepth * 0.17;
  const kneeY = 0.68 + squatDepth * 0.05;
  const kneeOut = 0.03 + squatDepth * 0.08;
  return {
    left_shoulder: { x: 0.43 - squatDepth * 0.03, y: 0.27 + squatDepth * 0.08 },
    right_shoulder: { x: 0.57 - squatDepth * 0.03, y: 0.27 + squatDepth * 0.08 },
    left_elbow: { x: 0.37, y: 0.42 },
    right_elbow: { x: 0.63, y: 0.42 },
    left_wrist: { x: 0.36, y: 0.56 },
    right_wrist: { x: 0.64, y: 0.56 },
    left_hip: { x: 0.44, y: hipY },
    right_hip: { x: 0.56, y: hipY },
    left_knee: { x: 0.43 - kneeOut, y: kneeY },
    right_knee: { x: 0.57 + kneeOut, y: kneeY },
    left_ankle: { x: 0.38, y: 0.9 },
    right_ankle: { x: 0.62, y: 0.9 }
  };
}

function curlPose(t: number): PoseLandmarks {
  const cycle = wave(t, 2.2);
  const wristY = 0.74 - cycle * 0.38;
  const wristIn = cycle * 0.05;
  return {
    left_shoulder: { x: 0.42, y: 0.28 },
    right_shoulder: { x: 0.58, y: 0.28 },
    left_elbow: { x: 0.42, y: 0.5 },
    right_elbow: { x: 0.58, y: 0.5 },
    left_wrist: { x: 0.42 + wristIn, y: wristY },
    right_wrist: { x: 0.58 - wristIn, y: wristY },
    left_hip: { x: 0.43, y: 0.6 },
    right_hip: { x: 0.57, y: 0.6 },
    left_knee: { x: 0.43, y: 0.78 },
    right_knee: { x: 0.57, y: 0.78 },
    left_ankle: { x: 0.43, y: 0.94 },
    right_ankle: { x: 0.57, y: 0.94 }
  };
}

function pushUpPose(t: number): PoseLandmarks {
  const cycle = wave(t, 2.4);
  const elbowBend = cycle * 0.1;
  const shoulderDrop = cycle * 0.08;
  return {
    left_shoulder: { x: 0.26, y: 0.5 + shoulderDrop },
    right_shoulder: { x: 0.26, y: 0.54 + shoulderDrop },
    left_elbow: { x: 0.18 + elbowBend, y: 0.62 },
    right_elbow: { x: 0.18 + elbowBend, y: 0.66 },
    left_wrist: { x: 0.16, y: 0.74 },
    right_wrist: { x: 0.16, y: 0.76 },
    left_hip: { x: 0.5, y: 0.54 + shoulderDrop * 0.35 },
    right_hip: { x: 0.5, y: 0.58 + shoulderDrop * 0.35 },
    left_knee: { x: 0.67, y: 0.57 },
    right_knee: { x: 0.67, y: 0.61 },
    left_ankle: { x: 0.84, y: 0.61 },
    right_ankle: { x: 0.84, y: 0.65 }
  };
}

function wallSitPose(t: number): PoseLandmarks {
  const wobble = Math.sin(t * 1.4) * 0.01;
  return {
    left_shoulder: { x: 0.4, y: 0.34 + wobble },
    right_shoulder: { x: 0.48, y: 0.34 + wobble },
    left_elbow: { x: 0.37, y: 0.5 },
    right_elbow: { x: 0.51, y: 0.5 },
    left_wrist: { x: 0.37, y: 0.64 },
    right_wrist: { x: 0.51, y: 0.64 },
    left_hip: { x: 0.4, y: 0.62 },
    right_hip: { x: 0.48, y: 0.62 },
    left_knee: { x: 0.6, y: 0.62 },
    right_knee: { x: 0.68, y: 0.62 },
    left_ankle: { x: 0.6, y: 0.86 },
    right_ankle: { x: 0.68, y: 0.86 }
  };
}

function treePose(t: number): PoseLandmarks {
  const wobble = Math.sin(t * 1.2) * 0.01;
  return {
    left_shoulder: { x: 0.43 + wobble, y: 0.28 },
    right_shoulder: { x: 0.57 + wobble, y: 0.28 },
    left_elbow: { x: 0.39 + wobble, y: 0.16 },
    right_elbow: { x: 0.61 + wobble, y: 0.16 },
    left_wrist: { x: 0.47 + wobble, y: 0.08 },
    right_wrist: { x: 0.53 + wobble, y: 0.08 },
    left_hip: { x: 0.46 + wobble, y: 0.5 },
    right_hip: { x: 0.54 + wobble, y: 0.5 },
    left_knee: { x: 0.48 + wobble, y: 0.68 },
    right_knee: { x: 0.7 + wobble, y: 0.58 },
    left_ankle: { x: 0.49 + wobble, y: 0.9 },
    right_ankle: { x: 0.53 + wobble, y: 0.68 }
  };
}

function plankPose(t: number): PoseLandmarks {
  const wobble = Math.sin(t * 1.7) * 0.018;
  return {
    left_shoulder: { x: 0.26, y: 0.5 },
    right_shoulder: { x: 0.26, y: 0.54 },
    left_elbow: { x: 0.18, y: 0.62 },
    right_elbow: { x: 0.18, y: 0.66 },
    left_wrist: { x: 0.16, y: 0.74 },
    right_wrist: { x: 0.16, y: 0.76 },
    left_hip: { x: 0.5, y: 0.54 + wobble },
    right_hip: { x: 0.5, y: 0.58 + wobble },
    left_knee: { x: 0.67, y: 0.57 },
    right_knee: { x: 0.67, y: 0.61 },
    left_ankle: { x: 0.84, y: 0.61 },
    right_ankle: { x: 0.84, y: 0.65 }
  };
}

function wave(t: number, duration: number) {
  return (1 - Math.cos((t / duration) * Math.PI * 2)) / 2;
}
