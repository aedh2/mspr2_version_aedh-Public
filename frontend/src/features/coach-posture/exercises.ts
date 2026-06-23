import type { ExerciseConfig, ExerciseId, PoseLandmarkName, PoseLandmarks } from "./types";

export const POSE_CONNECTIONS: Array<[PoseLandmarkName, PoseLandmarkName]> = [
  ["left_shoulder", "right_shoulder"],
  ["left_shoulder", "left_elbow"],
  ["left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow"],
  ["right_elbow", "right_wrist"],
  ["left_shoulder", "left_hip"],
  ["right_shoulder", "right_hip"],
  ["left_hip", "right_hip"],
  ["left_hip", "left_knee"],
  ["left_knee", "left_ankle"],
  ["right_hip", "right_knee"],
  ["right_knee", "right_ankle"]
];

const squatGuide: PoseLandmarks = {
  left_shoulder: { x: 0.42, y: 0.28 },
  right_shoulder: { x: 0.58, y: 0.28 },
  left_hip: { x: 0.43, y: 0.52 },
  right_hip: { x: 0.57, y: 0.52 },
  left_knee: { x: 0.37, y: 0.72 },
  right_knee: { x: 0.63, y: 0.72 },
  left_ankle: { x: 0.34, y: 0.9 },
  right_ankle: { x: 0.66, y: 0.9 },
  left_elbow: { x: 0.37, y: 0.43 },
  right_elbow: { x: 0.63, y: 0.43 },
  left_wrist: { x: 0.36, y: 0.58 },
  right_wrist: { x: 0.64, y: 0.58 }
};

const curlGuide: PoseLandmarks = {
  left_shoulder: { x: 0.42, y: 0.28 },
  right_shoulder: { x: 0.58, y: 0.28 },
  left_elbow: { x: 0.41, y: 0.48 },
  right_elbow: { x: 0.59, y: 0.48 },
  left_wrist: { x: 0.45, y: 0.38 },
  right_wrist: { x: 0.55, y: 0.38 },
  left_hip: { x: 0.43, y: 0.58 },
  right_hip: { x: 0.57, y: 0.58 },
  left_knee: { x: 0.43, y: 0.76 },
  right_knee: { x: 0.57, y: 0.76 },
  left_ankle: { x: 0.43, y: 0.93 },
  right_ankle: { x: 0.57, y: 0.93 }
};

const pushUpGuide: PoseLandmarks = {
  left_shoulder: { x: 0.27, y: 0.48 },
  right_shoulder: { x: 0.27, y: 0.52 },
  left_elbow: { x: 0.2, y: 0.6 },
  right_elbow: { x: 0.2, y: 0.64 },
  left_wrist: { x: 0.16, y: 0.72 },
  right_wrist: { x: 0.16, y: 0.76 },
  left_hip: { x: 0.5, y: 0.53 },
  right_hip: { x: 0.5, y: 0.57 },
  left_knee: { x: 0.67, y: 0.56 },
  right_knee: { x: 0.67, y: 0.6 },
  left_ankle: { x: 0.84, y: 0.6 },
  right_ankle: { x: 0.84, y: 0.64 }
};

const plankGuide: PoseLandmarks = {
  left_shoulder: { x: 0.27, y: 0.46 },
  right_shoulder: { x: 0.27, y: 0.5 },
  left_elbow: { x: 0.2, y: 0.6 },
  right_elbow: { x: 0.2, y: 0.64 },
  left_wrist: { x: 0.18, y: 0.72 },
  right_wrist: { x: 0.18, y: 0.74 },
  left_hip: { x: 0.5, y: 0.52 },
  right_hip: { x: 0.5, y: 0.56 },
  left_knee: { x: 0.67, y: 0.56 },
  right_knee: { x: 0.67, y: 0.6 },
  left_ankle: { x: 0.83, y: 0.6 },
  right_ankle: { x: 0.83, y: 0.64 }
};

const wallSitGuide: PoseLandmarks = {
  left_shoulder: { x: 0.4, y: 0.34 },
  right_shoulder: { x: 0.48, y: 0.34 },
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

const treePoseGuide: PoseLandmarks = {
  left_shoulder: { x: 0.43, y: 0.28 },
  right_shoulder: { x: 0.57, y: 0.28 },
  left_elbow: { x: 0.39, y: 0.16 },
  right_elbow: { x: 0.61, y: 0.16 },
  left_wrist: { x: 0.47, y: 0.08 },
  right_wrist: { x: 0.53, y: 0.08 },
  left_hip: { x: 0.46, y: 0.5 },
  right_hip: { x: 0.54, y: 0.5 },
  left_knee: { x: 0.48, y: 0.68 },
  left_ankle: { x: 0.49, y: 0.9 },
  right_knee: { x: 0.7, y: 0.58 },
  right_ankle: { x: 0.53, y: 0.68 }
};

export const COACH_EXERCISES: Record<ExerciseId, ExerciseConfig> = {
  squat: {
    id: "squat",
    name: "Squat",
    type: "dynamic",
    trackedJoints: ["genoux", "hanches", "buste"],
    requiredLandmarks: ["left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"],
    targetRepsPerSet: 10,
    correctThreshold: 78,
    almostThreshold: 58,
    instructions: [
      "Pieds largeur hanches, regard devant.",
      "Descends les hanches vers l'arriere.",
      "Garde les genoux alignes avec les pieds.",
      "Remonte completement pour valider une repetition."
    ],
    guide: squatGuide
  },
  curl_biceps: {
    id: "curl_biceps",
    name: "Curl biceps",
    type: "dynamic",
    trackedJoints: ["coudes", "poignets", "epaules"],
    requiredLandmarks: ["left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist"],
    targetRepsPerSet: 12,
    correctThreshold: 76,
    almostThreshold: 55,
    instructions: [
      "Garde les coudes proches du buste.",
      "Monte les mains sans balancer les epaules.",
      "Controle la descente jusqu'a extension presque complete."
    ],
    guide: curlGuide
  },
  push_up: {
    id: "push_up",
    name: "Pompes",
    type: "dynamic",
    trackedJoints: ["epaules", "coudes", "hanches", "chevilles"],
    requiredLandmarks: [
      "left_shoulder",
      "right_shoulder",
      "left_elbow",
      "right_elbow",
      "left_wrist",
      "right_wrist",
      "left_hip",
      "right_hip",
      "left_ankle",
      "right_ankle"
    ],
    targetRepsPerSet: 10,
    correctThreshold: 76,
    almostThreshold: 56,
    instructions: [
      "Aligne epaules, hanches et chevilles.",
      "Descends en gardant les coudes controles.",
      "Remonte completement pour valider la repetition."
    ],
    guide: pushUpGuide
  },
  gainage: {
    id: "gainage",
    name: "Gainage",
    type: "static",
    trackedJoints: ["epaules", "hanches", "chevilles"],
    requiredLandmarks: ["left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_ankle", "right_ankle"],
    targetRepsPerSet: 1,
    correctThreshold: 80,
    almostThreshold: 62,
    instructions: [
      "Aligne epaules, hanches et chevilles.",
      "Rentre legerement le bassin.",
      "Le chrono avance uniquement quand la posture est correcte."
    ],
    guide: plankGuide
  },
  wall_sit: {
    id: "wall_sit",
    name: "Chaise contre mur",
    type: "static",
    trackedJoints: ["dos", "hanches", "genoux", "chevilles"],
    requiredLandmarks: ["left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"],
    targetRepsPerSet: 1,
    correctThreshold: 78,
    almostThreshold: 60,
    instructions: [
      "Garde le dos droit.",
      "Flechis les genoux autour de 90 degres.",
      "Maintiens la position sans rebondir.",
      "Respire regulierement."
    ],
    guide: wallSitGuide
  },
  tree_pose: {
    id: "tree_pose",
    name: "Posture de l'arbre",
    type: "static",
    trackedJoints: ["buste", "hanches", "genoux", "chevilles", "poignets"],
    requiredLandmarks: ["left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"],
    targetRepsPerSet: 1,
    correctThreshold: 76,
    almostThreshold: 58,
    instructions: [
      "Stabilise la jambe d'appui.",
      "Place un pied contre la jambe opposee.",
      "Redresse le buste et garde les epaules stables.",
      "Leve les bras ou les mains au-dessus de la tete quand ils sont visibles.",
      "Le chrono avance uniquement quand l'equilibre est correct."
    ],
    guide: treePoseGuide
  }
};

export const COACH_EXERCISE_OPTIONS = Object.values(COACH_EXERCISES).filter((exercise) => exercise.id !== "push_up");
