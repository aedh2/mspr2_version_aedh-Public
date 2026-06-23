import { POSE_CONNECTIONS } from "./exercises";
import type { ExerciseConfig, HandLandmarks, PoseLandmarks, PosePoint, PostureStatus } from "./types";

const HAND_CONNECTIONS: Array<[number, number]> = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 4],
  [0, 5],
  [5, 6],
  [6, 7],
  [7, 8],
  [5, 9],
  [9, 10],
  [10, 11],
  [11, 12],
  [9, 13],
  [13, 14],
  [14, 15],
  [15, 16],
  [13, 17],
  [17, 18],
  [18, 19],
  [19, 20],
  [0, 17]
];

export function drawPostureOverlay(
  canvas: HTMLCanvasElement,
  current: PoseLandmarks | null,
  exercise: ExerciseConfig,
  status: PostureStatus,
  sourceMode: "mediapipe" | "simulation" = "mediapipe",
  handLandmarks: HandLandmarks[] = [],
  options: { showGuide?: boolean; handGestureActive?: boolean } = {}
) {
  const context = canvas.getContext("2d");
  if (!context) return;

  const width = canvas.width;
  const height = canvas.height;
  context.clearRect(0, 0, width, height);

  if (options.showGuide !== false) {
    drawSkeleton(context, exercise.guide, width, height, "#94a3b8", 2, 0.38, true);
  }
  if (current) {
    const currentColor = colorForStatus(status);
    drawSkeleton(context, current, width, height, currentColor, 5, 1, false);
  }
  handLandmarks.forEach((hand) => drawHandSkeleton(context, hand, width, height, options.handGestureActive === true));

  drawStatusPill(context, status, width, sourceMode);
}

function drawSkeleton(
  context: CanvasRenderingContext2D,
  landmarks: PoseLandmarks,
  width: number,
  height: number,
  color: string,
  lineWidth: number,
  alpha: number,
  dashed: boolean
) {
  context.save();
  context.globalAlpha = alpha;
  context.strokeStyle = color;
  context.fillStyle = color;
  context.lineWidth = lineWidth;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.setLineDash(dashed ? [10, 10] : []);

  for (const [from, to] of POSE_CONNECTIONS) {
    const start = landmarks[from];
    const end = landmarks[to];
    if (!start || !end) continue;
    context.beginPath();
    context.moveTo(start.x * width, start.y * height);
    context.lineTo(end.x * width, end.y * height);
    context.stroke();
  }

  Object.values(landmarks).forEach((point) => {
    if (point) drawPoint(context, point, width, height);
  });

  context.restore();
}

function drawHandSkeleton(context: CanvasRenderingContext2D, landmarks: HandLandmarks, width: number, height: number, gestureActive: boolean) {
  if (landmarks.length < 21) return;
  context.save();
  context.globalAlpha = 0.82;
  context.strokeStyle = gestureActive ? "#f97316" : "#38bdf8";
  context.fillStyle = gestureActive ? "#fed7aa" : "#bae6fd";
  context.lineWidth = 2.5;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.setLineDash([]);

  for (const [from, to] of HAND_CONNECTIONS) {
    const start = landmarks[from];
    const end = landmarks[to];
    if (!start || !end) continue;
    context.beginPath();
    context.moveTo(start.x * width, start.y * height);
    context.lineTo(end.x * width, end.y * height);
    context.stroke();
  }

  landmarks.forEach((point) => drawPoint(context, point, width, height, 3.5));
  context.restore();
}

function drawPoint(context: CanvasRenderingContext2D, point: PosePoint, width: number, height: number, radius = 5) {
  context.beginPath();
  context.arc(point.x * width, point.y * height, radius, 0, Math.PI * 2);
  context.fill();
}

function drawStatusPill(context: CanvasRenderingContext2D, status: PostureStatus, width: number, sourceMode: "mediapipe" | "simulation") {
  const label = status === "correct" ? "CORRECT" : status === "almost" ? "PRESQUE" : "INCORRECT";
  const color = colorForStatus(status);
  const modeLabel = sourceMode === "simulation" ? "SIMULATION" : label;
  context.save();
  context.font = "700 13px sans-serif";
  const textWidth = context.measureText(modeLabel).width;
  const pillWidth = textWidth + 28;
  const x = width - pillWidth - 16;
  const y = 16;
  context.fillStyle = "rgba(255,255,255,.92)";
  roundRect(context, x, y, pillWidth, 30, 15);
  context.fill();
  context.fillStyle = sourceMode === "simulation" ? "#b45309" : color;
  context.fillText(modeLabel, x + 14, y + 20);
  context.restore();
}

function colorForStatus(status: PostureStatus) {
  if (status === "correct") return "#22c55e";
  if (status === "almost") return "#eab308";
  return "#ef4444";
}

function roundRect(context: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.arcTo(x + width, y, x + width, y + height, radius);
  context.arcTo(x + width, y + height, x, y + height, radius);
  context.arcTo(x, y + height, x, y, radius);
  context.arcTo(x, y, x + width, y, radius);
  context.closePath();
}
