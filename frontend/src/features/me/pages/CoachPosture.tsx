"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Activity, Camera, Dumbbell, Hand, Maximize2, Minimize2, Pause, Play, RotateCcw, Save, Square, Timer, Trophy, Zap } from "lucide-react";
import type { ComponentType } from "react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/src/components/ui/button";
import { StatusBadge } from "@/src/components/ui/badge";
import { getCoachPostureHistory, requestCoachPostureFeedback, validateCoachPostureExercise } from "@/src/features/coach-posture/api";
import { drawPostureOverlay } from "@/src/features/coach-posture/drawing";
import { COACH_EXERCISES, COACH_EXERCISE_OPTIONS } from "@/src/features/coach-posture/exercises";
import { createInitialExerciseSessions, evaluatePosture, validateStaticHold } from "@/src/features/coach-posture/logic";
import { createPoseDetector, createSimulationPoseDetector, type PoseDetector } from "@/src/features/coach-posture/pose-engine";
import type {
  CoachPostureFeedback,
  CoachPostureHistoryItem,
  CoachPostureValidationRequest,
  DetectionStatus,
  ExerciseId,
  HandGesture,
  HandLandmarks,
  PostureEvaluation,
  PostureSession
} from "@/src/features/coach-posture/types";
import { Page } from "./_shared";

type CameraState = "idle" | "loading" | "ready" | "simulation" | "error";
const HAND_GESTURE_HIGHLIGHT_MS = 450;
const SNAPSHOT_MAX_WIDTH = 640;
type FeedbackMutationInput = {
  exerciseId: ExerciseId;
  evaluation: PostureEvaluation;
  personDetected: boolean;
  source: "manual" | "gesture";
};
type ValidationHistoryItem = CoachPostureHistoryItem;

export function CoachPosturePage() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const videoShellRef = useRef<HTMLDivElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const frameRef = useRef<number | null>(null);
  const detectorRef = useRef<PoseDetector | null>(null);
  const lastFrameAtRef = useRef<number | null>(null);
  const initialSessionsRef = useRef(createInitialExerciseSessions());
  const exerciseSessionsRef = useRef(initialSessionsRef.current);
  const missedFramesRef = useRef(0);
  const okGestureStartedAtRef = useRef<number | null>(null);
  const lastOkGestureTriggerAtRef = useRef(0);
  const okGestureArmedRef = useRef(true);
  const pauseGestureStartedAtRef = useRef<number | null>(null);
  const lastPauseGestureTriggerAtRef = useRef(0);
  const pauseGestureArmedRef = useRef(true);
  const peaceGestureStartedAtRef = useRef<number | null>(null);
  const lastPeaceGestureTriggerAtRef = useRef(0);
  const peaceGestureArmedRef = useRef(true);
  const handGestureHighlightUntilRef = useRef(0);
  const isPausedRef = useRef(false);
  const evaluationsRef = useRef<Partial<Record<ExerciseId, PostureEvaluation>>>({});

  const [exerciseId, setExerciseId] = useState<ExerciseId>("squat");
  const [cameraState, setCameraState] = useState<CameraState>("idle");
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [exerciseSessions, setExerciseSessions] = useState(initialSessionsRef.current);
  const [evaluations, setEvaluations] = useState<Partial<Record<ExerciseId, PostureEvaluation>>>({});
  const [feedbackByExercise, setFeedbackByExercise] = useState<Partial<Record<ExerciseId, CoachPostureFeedback>>>({});
  const [detectorMode, setDetectorMode] = useState<"loading" | "mediapipe" | "simulation">("loading");
  const [detectorMessage, setDetectorMessage] = useState<string | null>(null);
  const [detectionStatus, setDetectionStatus] = useState<DetectionStatus>("none");
  const [validationHistory, setValidationHistory] = useState<ValidationHistoryItem[]>([]);
  const [validationMessage, setValidationMessage] = useState<string | null>(null);
  const [gestureMessage, setGestureMessage] = useState<string | null>(null);
  const [lastGesture, setLastGesture] = useState<HandGesture>(null);
  const [lastHandLandmarks, setLastHandLandmarks] = useState<HandLandmarks[]>([]);
  const [snapshotDataUrl, setSnapshotDataUrl] = useState<string | null>(null);
  const [selectedSnapshot, setSelectedSnapshot] = useState<string | null>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fullscreenMessage, setFullscreenMessage] = useState<string | null>(null);

  const exercise = COACH_EXERCISES[exerciseId];
  const session = exerciseSessions[exerciseId];
  const evaluation = evaluations[exerciseId] || null;
  const feedback = feedbackByExercise[exerciseId] || null;
  const isActive = cameraState === "ready" || cameraState === "simulation";
  const isStaticExercise = exercise.type === "static";

  const historyQuery = useQuery({
    queryKey: ["coach-posture-history"],
    queryFn: getCoachPostureHistory,
    staleTime: 30_000
  });
  const displayedHistory = mergeValidationHistory(validationHistory, historyQuery.data || []);

  const feedbackMutation = useMutation({
    mutationFn: ({ exerciseId: targetExerciseId, evaluation: current, personDetected }: FeedbackMutationInput) => {
      return requestCoachPostureFeedback({
        exercise: targetExerciseId,
        status: current.status,
        angles: current.angles,
        detected_errors: current.detectedErrors,
        reps: current.session.reps,
        reps_in_current_set: current.session.repsInCurrentSet,
        sets: current.session.sets,
        hold_seconds: Math.floor(current.session.holdSeconds),
        best_hold_seconds: Math.floor(current.session.bestHoldSeconds),
        validated_holds: current.session.validatedHolds.map((hold) => Math.floor(hold)),
        score_alignement: current.score,
        person_detected: personDetected
      });
    },
    onSuccess: (nextFeedback, variables) => {
      setFeedbackByExercise((current) => ({ ...current, [variables.exerciseId]: nextFeedback }));
      if (variables.source === "gesture") {
        setGestureMessage("👌 Geste OK détecté — analyse lancée");
      }
    }
  });

  const validationMutation = useMutation({
    mutationFn: (payload: CoachPostureValidationRequest) => validateCoachPostureExercise(payload),
    onSuccess: (response, payload) => {
      setValidationHistory((current) => [
        {
          ...response,
          validated_at: payload.validated_at || new Date().toISOString(),
          exercise_label: payload.exercise_label,
          type: payload.type,
          status: payload.status,
          detected_errors: payload.detected_errors,
          snapshot_data_url: payload.snapshot_base64 || null
        },
        ...current
      ].slice(0, 8));
      setValidationMessage("Exercice valide et enregistre.");
      void historyQuery.refetch();
      setSnapshotDataUrl(null);
      resetCurrentExercise();
    },
    onError: (error) => {
      setValidationMessage(error instanceof Error ? error.message : "Impossible de valider l'exercice.");
    }
  });

  useEffect(() => {
    if (!isActive) {
      stopAnimationLoop();
      return;
    }
    let cancelled = false;

    async function tick(timestamp: number) {
      if (cancelled) return;
      await ensureDetector();
      const detector = detectorRef.current;
      const canvas = canvasRef.current;
      if (!detector || !canvas) {
        frameRef.current = requestAnimationFrame(tick);
        return;
      }

      const video = cameraState === "ready" ? videoRef.current : null;
      sizeCanvas(canvas, video);
      const rawDeltaSeconds = lastFrameAtRef.current ? Math.min(0.25, (timestamp - lastFrameAtRef.current) / 1000) : 0;
      lastFrameAtRef.current = timestamp;
      const deltaSeconds = isPausedRef.current ? 0 : rawDeltaSeconds;
      const currentSession = exerciseSessionsRef.current[exerciseId];
      const handDetection = await detector.detectHand?.(video, timestamp) || { landmarks: [], gesture: null };
      setLastHandLandmarks(handDetection.landmarks);
      if (handDetection.gesture) {
        setLastGesture(handDetection.gesture);
        handGestureHighlightUntilRef.current = timestamp + HAND_GESTURE_HIGHLIGHT_MS;
      }
      const handGestureActive = timestamp < handGestureHighlightUntilRef.current;
      handlePauseGesture(handDetection.gesture === "pause", timestamp);
      handlePeaceGesture(handDetection.gesture === "peace", timestamp, detector.mode);

      let pose = null;
      try {
        pose = await detector.estimate(video, exerciseId, timestamp);
      } catch (error) {
        const fallback = createSimulationPoseDetector(formatDetectorError(error));
        detectorRef.current = fallback;
        setDetectorMode(fallback.mode);
        setDetectorMessage(fallback.setupError || null);
        pose = await fallback.estimate(null, exerciseId, timestamp);
      }
      if (!pose) {
        missedFramesRef.current += 1;
        if (missedFramesRef.current >= 3) {
          setDetectionStatus("none");
        }
        handleOkGesture(
          handDetection.gesture === "ok",
          evaluationsRef.current[exerciseId] || null,
          timestamp,
          detector.mode,
          false
        );
        drawPostureOverlay(canvas, null, exercise, currentSession.status, detector.mode, handDetection.landmarks, {
          showGuide: !isPausedRef.current,
          handGestureActive
        });
        frameRef.current = requestAnimationFrame(tick);
        return;
      }
      missedFramesRef.current = 0;

      if (isPausedRef.current) {
        drawPostureOverlay(canvas, pose, exercise, currentSession.status, detector.mode, handDetection.landmarks, {
          showGuide: false,
          handGestureActive
        });
        frameRef.current = requestAnimationFrame(tick);
        return;
      }

      const nextEvaluation = evaluatePosture(exercise, pose, currentSession, deltaSeconds, timestamp);
      const nextSessions = { ...exerciseSessionsRef.current, [exerciseId]: nextEvaluation.session };
      exerciseSessionsRef.current = nextSessions;
      setExerciseSessions(nextSessions);
      evaluationsRef.current = { ...evaluationsRef.current, [exerciseId]: nextEvaluation };
      setEvaluations(evaluationsRef.current);
      setDetectionStatus(nextEvaluation.detectionStatus);
      handleOkGesture(handDetection.gesture === "ok", nextEvaluation, timestamp, detector.mode, true);
      drawPostureOverlay(canvas, pose, exercise, nextEvaluation.status, detector.mode, handDetection.landmarks, {
        handGestureActive
      });
      frameRef.current = requestAnimationFrame(tick);
    }

    frameRef.current = requestAnimationFrame(tick);
    return () => {
      cancelled = true;
      stopAnimationLoop();
    };
  }, [cameraState, exercise, exerciseId, isActive]);

  useEffect(() => {
    return () => {
      stopCamera();
      detectorRef.current?.dispose();
    };
  }, []);

  useEffect(() => {
    if (!selectedSnapshot) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setSelectedSnapshot(null);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedSnapshot]);

  useEffect(() => {
    function onFullscreenChange() {
      setIsFullscreen(document.fullscreenElement === videoShellRef.current);
      if (document.fullscreenElement === videoShellRef.current) {
        setFullscreenMessage(null);
      }
    }
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, []);

  useEffect(() => {
    if (!gestureMessage) return;
    const timeout = window.setTimeout(() => setGestureMessage(null), 3500);
    return () => window.clearTimeout(timeout);
  }, [gestureMessage]);

  async function ensureDetector() {
    if (detectorRef.current) return;
    const detector = await createPoseDetector();
    detectorRef.current = detector;
    setDetectorMode(detector.mode);
    setDetectorMessage(detector.setupError || null);
  }

  async function startCamera() {
    setCameraError(null);
    setCameraState("loading");
    stopAnimationLoop();

    if (typeof window === "undefined") return;
    const isLocalhost = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
    if (!window.isSecureContext && !isLocalhost) {
      setCameraState("error");
      setCameraError("La camera exige HTTPS ou localhost.");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraState("error");
      setCameraError("Ce navigateur ne supporte pas getUserMedia.");
      return;
    }

    stopCamera();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "user" }, width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false
      });
      streamRef.current = stream;
      if (!videoRef.current) throw new Error("Bloc video indisponible.");
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      await ensureDetector();
      setCameraState("ready");
    } catch (error) {
      setCameraState("error");
      setCameraError(formatCameraError(error));
    }
  }

  function startSimulation() {
    stopCamera();
    detectorRef.current?.dispose();
    const detector = createSimulationPoseDetector("Mode simulation active manuellement.");
    detectorRef.current = detector;
    setDetectorMode(detector.mode);
    setDetectorMessage(detector.setupError || null);
    setCameraError(null);
    missedFramesRef.current = 0;
    setDetectionStatus("detected");
    setLastHandLandmarks([]);
    setLastGesture(null);
    setCameraState("simulation");
  }

  function stopCamera() {
    stopAnimationLoop();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    if (cameraState !== "idle") {
      setCameraState("idle");
    }
    missedFramesRef.current = 0;
    setDetectionStatus("none");
    setLastHandLandmarks([]);
    setLastGesture(null);
    setSnapshotDataUrl(null);
    setSelectedSnapshot(null);
    setPaused(false, "Session arretee.");
  }

  function stopAnimationLoop() {
    if (frameRef.current) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
    lastFrameAtRef.current = null;
  }

  function updateExerciseSession(id: ExerciseId, updater: (current: PostureSession) => PostureSession) {
    const nextSessions = {
      ...exerciseSessionsRef.current,
      [id]: updater(exerciseSessionsRef.current[id])
    };
    exerciseSessionsRef.current = nextSessions;
    setExerciseSessions(nextSessions);
  }

  function resetCurrentExercise() {
    updateExerciseSession(exerciseId, () => createInitialExerciseSessions()[exerciseId]);
    evaluationsRef.current = { ...evaluationsRef.current, [exerciseId]: undefined };
    setEvaluations(evaluationsRef.current);
    setFeedbackByExercise((current) => ({ ...current, [exerciseId]: undefined }));
    feedbackMutation.reset();
  }

  function resetAllExercises() {
    const nextSessions = createInitialExerciseSessions();
    exerciseSessionsRef.current = nextSessions;
    setExerciseSessions(nextSessions);
    evaluationsRef.current = {};
    setEvaluations({});
    setFeedbackByExercise({});
    feedbackMutation.reset();
  }

  function validateCurrentStaticHold() {
    if (!isStaticExercise) return;
    const currentSession = exerciseSessionsRef.current[exerciseId];
    if (currentSession.holdSeconds <= 0) return;
    const validatedSeconds = currentSession.holdSeconds;
    updateExerciseSession(exerciseId, validateStaticHold);
    evaluationsRef.current = { ...evaluationsRef.current, [exerciseId]: undefined };
    setEvaluations(evaluationsRef.current);
    lastFrameAtRef.current = null;
    setGestureMessage(`Temps valide : ${formatDuration(validatedSeconds)}. Serie remise a zero.`);
  }

  function triggerFeedbackAnalysis(source: "manual" | "gesture", currentEvaluation = evaluation, personDetected = detectionStatus !== "none") {
    if (!currentEvaluation || feedbackMutation.isPending) return;
    feedbackMutation.mutate({
      exerciseId,
      evaluation: currentEvaluation,
      personDetected,
      source
    });
  }

  function setPaused(paused: boolean, message?: string) {
    isPausedRef.current = paused;
    setIsPaused(paused);
    if (message) {
      setGestureMessage(message);
    }
  }

  function togglePause(source: "manual" | "gesture") {
    const nextPaused = !isPausedRef.current;
    setPaused(
      nextPaused,
      source === "gesture"
        ? nextPaused
          ? "🤟 Geste pause détecté — séance en pause"
          : "🤟 Geste pause détecté — reprise de la séance"
        : nextPaused
          ? "Session en pause."
          : "Session reprise."
    );
    lastFrameAtRef.current = null;
  }

  function handlePauseGesture(detected: boolean, timestamp: number) {
    if (!detected) {
      pauseGestureStartedAtRef.current = null;
      pauseGestureArmedRef.current = true;
      return;
    }
    if (!pauseGestureArmedRef.current) return;
    const cooledDown = timestamp - lastPauseGestureTriggerAtRef.current > 2600;
    if (cooledDown) {
      lastPauseGestureTriggerAtRef.current = timestamp;
      pauseGestureStartedAtRef.current = null;
      pauseGestureArmedRef.current = false;
      togglePause("gesture");
    }
  }

  async function toggleCameraFullscreen() {
    const element = videoShellRef.current;
    if (!element) {
      setFullscreenMessage("Bloc camera indisponible.");
      return;
    }
    if (!document.fullscreenEnabled) {
      setFullscreenMessage("Le plein ecran n'est pas supporte par ce navigateur.");
      return;
    }
    try {
      if (document.fullscreenElement === element) {
        await document.exitFullscreen();
      } else {
        await element.requestFullscreen();
      }
    } catch (error) {
      setFullscreenMessage(error instanceof Error ? error.message : "Impossible d'activer le plein ecran.");
    }
  }

  function handlePeaceGesture(detected: boolean, timestamp: number, sourceMode: "mediapipe" | "simulation") {
    if (!detected || sourceMode !== "mediapipe") {
      peaceGestureStartedAtRef.current = null;
      peaceGestureArmedRef.current = true;
      return;
    }
    if (!peaceGestureArmedRef.current) return;
    peaceGestureStartedAtRef.current ??= timestamp;
    const stableForMs = timestamp - peaceGestureStartedAtRef.current;
    const cooledDown = timestamp - lastPeaceGestureTriggerAtRef.current > 2000;
    if (stableForMs >= 700 && cooledDown) {
      lastPeaceGestureTriggerAtRef.current = timestamp;
      peaceGestureStartedAtRef.current = null;
      peaceGestureArmedRef.current = false;
      captureSnapshotFromVideo();
    }
  }

  function handleOkGesture(
    detected: boolean,
    currentEvaluation: PostureEvaluation | null,
    timestamp: number,
    sourceMode: "mediapipe" | "simulation",
    personDetected: boolean
  ) {
    if (!detected || sourceMode !== "mediapipe" || isPausedRef.current) {
      okGestureStartedAtRef.current = null;
      okGestureArmedRef.current = true;
      return;
    }
    if (!okGestureArmedRef.current) return;
    okGestureStartedAtRef.current ??= timestamp;
    const stableForMs = timestamp - okGestureStartedAtRef.current;
    const cooledDown = timestamp - lastOkGestureTriggerAtRef.current > 2200;
    if (stableForMs >= 700 && cooledDown && !feedbackMutation.isPending) {
      lastOkGestureTriggerAtRef.current = timestamp;
      okGestureStartedAtRef.current = null;
      okGestureArmedRef.current = false;
      if (currentEvaluation) {
        setGestureMessage("👌 Geste OK détecté — analyse lancée");
        triggerFeedbackAnalysis("gesture", currentEvaluation, personDetected);
      } else {
        setGestureMessage("Aucune posture exploitable pour le moment.");
      }
    }
  }

  function captureSnapshotFromVideo() {
    const video = videoRef.current;
    if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || !video.videoWidth || !video.videoHeight) {
      setGestureMessage("✌️ Geste peace détecté — caméra indisponible pour la photo");
      return;
    }
    const snapshotCanvas = document.createElement("canvas");
    const scale = Math.min(1, SNAPSHOT_MAX_WIDTH / video.videoWidth);
    snapshotCanvas.width = Math.round(video.videoWidth * scale);
    snapshotCanvas.height = Math.round(video.videoHeight * scale);
    const context = snapshotCanvas.getContext("2d");
    if (!context) return;
    context.translate(snapshotCanvas.width, 0);
    context.scale(-1, 1);
    context.drawImage(video, 0, 0, snapshotCanvas.width, snapshotCanvas.height);
    setSnapshotDataUrl(snapshotCanvas.toDataURL("image/jpeg", 0.72));
    setGestureMessage("✌️ Geste peace détecté — photo capturée");
  }

  function validateCurrentExercise() {
    const payload = validationPayload();
    if (!payload) {
      setValidationMessage("Aucune posture exploitable a valider.");
      return;
    }
    validationMutation.mutate(payload);
  }

  function validationPayload(): CoachPostureValidationRequest | null {
    const current = evaluation;
    if (!current) return null;
    const currentSession = current.session;
    const staticHoldSeconds = Math.floor(currentSession.holdSeconds || currentSession.validatedHolds.at(-1) || 0);
    return {
      exercise: exerciseId,
      exercise_label: exercise.name,
      type: exercise.type,
      reps: exercise.type === "static" ? 0 : currentSession.reps,
      reps_in_current_set: exercise.type === "static" ? 0 : currentSession.repsInCurrentSet,
      sets: exercise.type === "static" ? Math.max(currentSession.sets, staticHoldSeconds > 0 ? 1 : 0) : currentSession.sets,
      hold_seconds: exercise.type === "static" ? staticHoldSeconds : 0,
      best_hold_seconds: Math.floor(currentSession.bestHoldSeconds),
      validated_holds: currentSession.validatedHolds.length,
      score_alignement: current.score,
      status: current.status,
      detected_errors: current.detectedErrors,
      feedback: feedback ? {
        mode: feedback.mode,
        conseils: feedback.conseils,
        erreurs_principales: feedback.erreurs_principales,
        encouragement: feedback.encouragement
      } : undefined,
      snapshot_base64: snapshotDataUrl,
      validated_at: new Date().toISOString()
    };
  }

  return (
    <Page title="Coach posture" eyebrow="Sport & IA">
      <div className="posture-toolbar">
            <label className="field posture-exercise-field">
              <span>Exercice</span>
              <select
                className="control"
                value={exerciseId}
                onChange={(event) => setExerciseId(event.target.value as ExerciseId)}
              >
                {COACH_EXERCISE_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>{option.name}</option>
                ))}
              </select>
            </label>
            <div className="posture-actions">
              <Button onClick={() => void startCamera()} disabled={cameraState === "loading"}>
                <Camera size={16} />
                Demarrer la camera
              </Button>
              <Button variant="secondary" onClick={stopCamera} disabled={cameraState === "idle"}>
                <Square size={16} />
                Arreter la camera
              </Button>
              <Button variant="secondary" onClick={() => togglePause("manual")} disabled={!isActive}>
                {isPaused ? <Play size={16} /> : <Pause size={16} />}
                {isPaused ? "Reprendre" : "Pause"}
              </Button>
              {isStaticExercise ? (
                <Button variant="secondary" onClick={validateCurrentStaticHold} disabled={session.holdSeconds <= 0}>
                  <Trophy size={16} />
                  Terminer la serie
                </Button>
              ) : null}
              <Button variant="secondary" onClick={resetCurrentExercise}>
                <RotateCcw size={16} />
                Reinitialiser cet exercice
              </Button>
              <Button variant="secondary" onClick={resetAllExercises}>
                <RotateCcw size={16} />
                Tout reinitialiser
              </Button>
            </div>
          </div>

      <div className="posture-layout">
        <section className="posture-stage">
          <div ref={videoShellRef} className={`posture-video-shell posture-${evaluation?.status || "idle"}${isPaused ? " posture-video-paused" : ""}`}>
            <video
              ref={videoRef}
              className={`posture-video${cameraState === "ready" ? "" : " posture-video-hidden"}`}
              autoPlay
              playsInline
              muted
            />
            {cameraState === "simulation" ? <div className="posture-simulation-backdrop" /> : null}
            <canvas ref={canvasRef} className="posture-overlay" aria-label="Squelette posture actuel et guide cible" />
            <button
              className="posture-fullscreen-button"
              type="button"
              onClick={() => void toggleCameraFullscreen()}
              aria-label={isFullscreen ? "Quitter le plein ecran camera" : "Afficher la camera en plein ecran"}
            >
              {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
              <span>{isFullscreen ? "Quitter" : "Plein ecran"}</span>
            </button>
            <div className="posture-camera-hud" aria-live="polite">
              <strong>{exercise.name}</strong>
              <span>Statut : {statusLabel(evaluation?.status)}</span>
              {isStaticExercise ? (
                <>
                  <span>Temps : {formatDuration(session.holdSeconds)}</span>
                  <span>Meilleur : {formatDuration(session.bestHoldSeconds)}</span>
                  <span>Series validees : {session.validatedHolds.length}</span>
                </>
              ) : (
                <>
                  <span>Reps : {session.repsInCurrentSet} / {exercise.targetRepsPerSet}</span>
                  <span>Total reps : {session.reps}</span>
                  <span>Sets : {session.sets}</span>
                </>
              )}
              <span>Score : {evaluation?.score ?? 0}%</span>
              <span>Mode : {detectorModeLabel(detectorMode)}</span>
              <span>{detectionStatusLabel(detectionStatus, isActive)}</span>
              <span>{lastHandLandmarks.length ? "Main detectee" : "Main non detectee"}</span>
              {lastGesture ? <span>Geste : {gestureLabel(lastGesture)}</span> : null}
              {snapshotDataUrl ? <span>Photo capturee</span> : null}
              {isPaused ? <span>Session en pause</span> : null}
            </div>
            {isPaused ? (
              <div className="posture-pause-banner">
                <Pause size={18} />
                <strong>Session en pause</strong>
              </div>
            ) : null}
            {!isActive ? (
              <div className="posture-video-state">
                <Dumbbell size={26} />
                <strong>{cameraState === "error" ? "Camera indisponible" : "Pret pour la seance"}</strong>
                <span>{cameraError || "Demarrez la camera ou utilisez la simulation si aucun appareil n'est disponible."}</span>
                {cameraState === "error" ? (
                  <Button variant="secondary" onClick={startSimulation}>
                    <Play size={16} />
                    Activer la simulation
                  </Button>
                ) : null}
              </div>
            ) : null}
            {isActive && detectionStatus !== "detected" ? (
              <div className={`posture-person-warning posture-person-${detectionStatus}`}>
                {detectionStatusLabel(detectionStatus, true)}
              </div>
            ) : null}
          </div>

          <div className="posture-underbar">
            <StatusBadge value={statusLabel(evaluation?.status)} />
            <span>Detection : {detectorModeLabel(detectorMode)}</span>
            <span>{cameraState === "simulation" ? "Mode simulation actif" : cameraState === "ready" ? "Flux camera actif" : "Camera arretee"}</span>
            <span>{lastHandLandmarks.length ? "Squelette main actif" : "Aucune main detectee"}</span>
            {lastGesture ? <span>Dernier geste : {gestureLabel(lastGesture)}</span> : null}
            {detectorMessage ? <span>{detectorMessage}</span> : null}
            {gestureMessage ? <span>{gestureMessage}</span> : null}
            {fullscreenMessage ? <span>{fullscreenMessage}</span> : null}
          </div>

          {isStaticExercise ? (
            <div className="posture-static-holds-inline">
              <strong>Temps valides</strong>
              {session.validatedHolds.length ? (
                <div>
                  {session.validatedHolds.slice(-5).map((hold, index) => (
                    <span key={`${hold}-${index}`}>{formatDuration(hold)}</span>
                  ))}
                </div>
              ) : (
                <span>Aucune serie statique validee.</span>
              )}
            </div>
          ) : null}

          <section className="chart-card posture-validation-history">
            <div className="chart-card-header">
              <div>
                <span className="eyebrow">Historique</span>
                <h2>Historique coach posture</h2>
              </div>
              <StatusBadge value={`${displayedHistory.length} enregistrements`} />
            </div>
            {displayedHistory.length ? (
              <div className="posture-validation-list">
                {displayedHistory.map((item) => (
                  <article key={item.validation_id}>
                    {renderHistorySnapshot(item, setSelectedSnapshot)}
                    <time>{formatTime(item.validated_at)}</time>
                    <strong>{item.exercise_label}</strong>
                    <span>{item.type === "static" ? "Statique" : "Dynamique"}</span>
                    <span>Reps {item.summary.reps}</span>
                    <span>Sets {item.summary.sets}</span>
                    <span>Chrono {formatDuration(item.summary.hold_seconds)}</span>
                    <span>Score {item.summary.score_alignement}%</span>
                    <span>{statusLabel(item.status)}</span>
                    <StatusBadge value="enregistre" />
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted">{historyQuery.isLoading ? "Chargement de l'historique..." : "Les validations enregistrees apparaitront ici."}</p>
            )}
          </section>
        </section>

        <aside className="posture-side">
          <section className="chart-card posture-score-card">
            <div className="posture-status-head">
              <div>
                <span className="eyebrow">Statut</span>
                <h2>{statusLabel(evaluation?.status)}</h2>
              </div>
              <strong>{evaluation?.score ?? 0}</strong>
            </div>
            <div className="posture-score-track">
              <span style={{ width: `${evaluation?.score ?? 0}%` }} />
            </div>
            <div className="posture-mini-grid">
              {isStaticExercise ? (
                <>
                  <Metric icon={Timer} label="Chrono" value={formatDuration(session.holdSeconds)} />
                  <Metric icon={Trophy} label="Meilleur" value={formatDuration(session.bestHoldSeconds)} />
                  <Metric icon={Activity} label="Series" value={session.validatedHolds.length} />
                </>
              ) : (
                <>
                  <Metric icon={Zap} label="Reps" value={session.reps} />
                  <Metric icon={Activity} label="Reps du set" value={`${session.repsInCurrentSet}/${exercise.targetRepsPerSet}`} />
                  <Metric icon={Timer} label="Sets" value={session.sets} />
                </>
              )}
            </div>
            {isStaticExercise ? (
              <Button variant="secondary" onClick={validateCurrentStaticHold} disabled={session.holdSeconds <= 0}>
                <Trophy size={16} />
                Valider le temps
              </Button>
            ) : null}
            <Button onClick={() => triggerFeedbackAnalysis("manual")} disabled={!evaluation || feedbackMutation.isPending}>
              <Zap size={16} />
              {feedbackMutation.isPending ? "Analyse..." : "Analyser ma posture"}
            </Button>
            <Button onClick={validateCurrentExercise} disabled={!evaluation || validationMutation.isPending}>
              <Save size={16} />
              {validationMutation.isPending ? "Validation..." : "Valider l'exercice"}
            </Button>
            <Button variant="secondary" onClick={() => togglePause("manual")} disabled={!isActive}>
              {isPaused ? <Play size={16} /> : <Pause size={16} />}
              {isPaused ? "Reprendre la seance" : "Mettre en pause"}
            </Button>
            <div className="posture-ok-hint">
              <Hand size={15} />
              <span>👌 OK : analyse. 🤟 pause/reprise. ✌️ peace : photo.</span>
            </div>
            {snapshotDataUrl ? (
              <div className="posture-snapshot-preview">
                <button type="button" onClick={() => setSelectedSnapshot(snapshotDataUrl)} aria-label="Ouvrir la photo capturee en plein ecran">
                  <img src={snapshotDataUrl} alt="Photo capturee pendant l'exercice" />
                </button>
                <span>Photo prete pour la validation</span>
              </div>
            ) : null}
            {feedbackMutation.isError ? <div className="form-error">{feedbackMutation.error.message}</div> : null}
            {validationMessage ? <div className={validationMutation.isError ? "form-error" : "form-success"}>{validationMessage}</div> : null}
          </section>
        </aside>
      </div>

      <div className="posture-details-grid">
          <section className="chart-card">
            <div className="chart-card-header">
              <div>
                <span className="eyebrow">Consignes</span>
                <h2>{exercise.name}</h2>
              </div>
              <StatusBadge value={exercise.type === "static" ? "Statique" : "Dynamique"} />
            </div>
            <ul className="posture-list">
              {exercise.instructions.map((instruction) => (
                <li key={instruction}>{instruction}</li>
              ))}
            </ul>
            <div className="posture-joints">
              {exercise.trackedJoints.map((joint) => <span key={joint}>{joint}</span>)}
            </div>
          </section>

          <section className="chart-card">
            <div className="chart-card-header">
              <div>
                <span className="eyebrow">Detection</span>
                <h2>{detectionStatusLabel(detectionStatus, isActive)}</h2>
              </div>
              <StatusBadge value={statusLabel(evaluation?.status)} />
            </div>
            {evaluation?.detectedErrors.length ? (
              <ul className="posture-list">
                {evaluation.detectedErrors.map((error) => <li key={error}>{error}</li>)}
              </ul>
            ) : (
              <p className="muted">{postureGuidance(exerciseId, evaluation, detectionStatus, isActive, isPaused)}</p>
            )}
            {evaluation?.missingLandmarks.length ? (
              <div className="posture-joints posture-joints-warning">
                {evaluation.missingLandmarks.map((joint) => <span key={joint}>{joint.replaceAll("_", " ")}</span>)}
              </div>
            ) : null}
          </section>

          {isStaticExercise ? (
            <section className="chart-card">
              <div className="chart-card-header">
                <div>
                  <span className="eyebrow">Historique</span>
                  <h2>Temps valides</h2>
                </div>
                <StatusBadge value={`${session.validatedHolds.length} series`} />
              </div>
              {session.validatedHolds.length ? (
                <div className="posture-history">
                  {session.validatedHolds.slice(-6).map((hold, index) => (
                    <span key={`${hold}-${index}`}>{formatDuration(hold)}</span>
                  ))}
                </div>
              ) : (
                <p className="muted">Aucun temps valide pour cet exercice.</p>
              )}
            </section>
          ) : null}

          <section className="chart-card">
            <div className="chart-card-header">
              <div>
                <span className="eyebrow">Feedback</span>
                <h2>{feedback ? feedback.encouragement : "En attente"}</h2>
              </div>
              {feedback ? <StatusBadge value={feedback.mode === "external" ? "DeepSeek" : "Local"} /> : null}
            </div>
            {feedback ? (
              <div className="posture-feedback">
                <strong>Conseils</strong>
                <ul className="posture-list">
                  {feedback.conseils.map((tip) => <li key={tip}>{tip}</li>)}
                </ul>
                {feedback.erreurs_principales.length ? (
                  <>
                    <strong>Points a corriger</strong>
                    <ul className="posture-list">
                      {feedback.erreurs_principales.map((error) => <li key={error}>{error}</li>)}
                    </ul>
                  </>
                ) : null}
                <span className="muted">{feedback.safety_warning}</span>
              </div>
            ) : (
              <p className="muted">Lancez une analyse pour recevoir un conseil texte base sur les angles et les compteurs calcules localement.</p>
            )}
          </section>
      </div>

      <section className="chart-card posture-gesture-guide">
        <div className="chart-card-header">
          <div>
            <span className="eyebrow">Gestes</span>
            <h2>Guide des gestes</h2>
          </div>
          <StatusBadge value={lastGesture ? `Dernier : ${gestureLabel(lastGesture)}` : "En attente"} />
        </div>
        <div className="posture-gesture-grid">
          <article>
            <Hand size={18} />
            <strong>Geste OK</strong>
            <span>Lance automatiquement l'analyse de posture.</span>
          </article>
          <article>
            <Pause size={18} />
            <strong>Geste 🤟</strong>
            <span>Pouce, index et auriculaire leves : met en pause ou reprend l'exercice.</span>
          </article>
          <article>
            <Camera size={18} />
            <strong>Geste ✌️</strong>
            <span>Index et majeur leves, annulaire et auriculaire replies : capture une photo.</span>
          </article>
        </div>
      </section>
      {selectedSnapshot ? (
        <div className="posture-snapshot-modal" role="dialog" aria-modal="true" aria-label="Photo capturee" onClick={() => setSelectedSnapshot(null)}>
          <div className="posture-snapshot-modal-content" onClick={(event) => event.stopPropagation()}>
            <button type="button" onClick={() => setSelectedSnapshot(null)} aria-label="Fermer la photo">Fermer</button>
            <img src={selectedSnapshot} alt="Photo capturee en plein ecran" />
          </div>
        </div>
      ) : null}
    </Page>
  );
}

function Metric({ icon: Icon, label, value }: { icon: ComponentType<{ size?: number }>; label: string; value: string | number }) {
  return (
    <div>
      <Icon size={16} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function sizeCanvas(canvas: HTMLCanvasElement, video: HTMLVideoElement | null) {
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(320, Math.round(rect.width || video?.videoWidth || 960));
  const height = Math.max(240, Math.round(rect.height || video?.videoHeight || 540));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
}

function statusLabel(status?: string) {
  if (status === "correct") return "correct";
  if (status === "almost") return "presque correct";
  if (status === "incorrect") return "incorrect";
  return "en attente";
}

function mergeValidationHistory(local: ValidationHistoryItem[], persisted: ValidationHistoryItem[]) {
  const seen = new Set<string>();
  return [...local, ...persisted].filter((item) => {
    if (seen.has(item.validation_id)) return false;
    seen.add(item.validation_id);
    return true;
  }).slice(0, 8);
}

function gestureLabel(gesture: HandGesture) {
  if (gesture === "ok") return "👌 OK";
  if (gesture === "pause") return "🤟 Pause";
  if (gesture === "peace") return "✌️ Photo";
  return "Aucun";
}

function historyImage(item: ValidationHistoryItem) {
  return item.snapshot_data_url || item.snapshot_path || null;
}

function renderHistorySnapshot(item: ValidationHistoryItem, selectSnapshot: (snapshot: string) => void) {
  const image = historyImage(item);
  if (!image) {
    return <span className="posture-history-placeholder">Photo</span>;
  }
  return (
    <button className="posture-history-image" type="button" onClick={() => selectSnapshot(image)}>
      <img src={image} alt="Photo de validation" />
    </button>
  );
}

function postureGuidance(
  exerciseId: ExerciseId,
  evaluation: PostureEvaluation | null,
  detectionStatus: DetectionStatus,
  isActive: boolean,
  isPaused: boolean
) {
  if (isPaused) return "Session en pause.";
  if (!isActive) return "Aucune personne detectee";
  if (detectionStatus === "none") return "Aucune personne detectee";
  if (detectionStatus === "partial") return "Posture partiellement detectee";
  if (exerciseId === "wall_sit" && evaluation?.status === "correct") {
    return "Position correcte, maintien en cours";
  }
  if (exerciseId === "tree_pose" && evaluation?.status === "correct") {
    return "Position correcte, maintien en cours";
  }
  return "Aucune erreur active detectee.";
}

function detectorModeLabel(mode: "loading" | "mediapipe" | "simulation") {
  if (mode === "mediapipe") return "Detection reelle MediaPipe active";
  if (mode === "simulation") return "Mode simulation";
  return "Initialisation MediaPipe";
}

function detectionStatusLabel(status: DetectionStatus, isActive: boolean) {
  if (!isActive) return "Detection en attente";
  if (status === "detected") return "Personne detectee";
  if (status === "partial") return "Posture partiellement detectee";
  return "Aucune personne detectee";
}

function formatDuration(seconds: number) {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  const remainingSeconds = safeSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function formatDetectorError(error: unknown) {
  if (error instanceof Error) {
    return `MediaPipe indisponible: ${error.message}`;
  }
  return "MediaPipe indisponible: mode simulation active.";
}

function formatCameraError(error: unknown) {
  if (error instanceof DOMException) {
    if (error.name === "NotAllowedError" || error.name === "SecurityError") {
      return "Permission camera refusee. Autorisez la camera dans le navigateur puis reessayez.";
    }
    if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
      return "Aucune camera disponible n'a ete detectee.";
    }
    if (error.name === "NotReadableError" || error.name === "TrackStartError") {
      return "La camera est deja utilisee ou inaccessible.";
    }
  }
  return error instanceof Error ? error.message : "Impossible d'activer la camera.";
}
