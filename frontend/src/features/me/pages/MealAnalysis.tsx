"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Camera, ImagePlus, RefreshCcw, ScanSearch, Sparkles, UtensilsCrossed } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { StatusBadge } from "@/src/components/ui/badge";
import { MetricCard } from "@/src/components/ui/cards";
import { Button } from "@/src/components/ui/button";
import { LoadingState } from "@/src/components/ui/states";
import { analyzeMealPhoto, getMealAnalysisConfig } from "@/src/features/meal-analysis/api";
import { formatNumber } from "@/src/lib/format";
import type { MealAnalysisResult } from "@/src/types/domain";
import { Page } from "./_shared";

type CameraState = "loading" | "ready" | "error";
type PhotoSource = "camera" | "file";

export function MealAnalysisPage() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [cameraState, setCameraState] = useState<CameraState>("loading");
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [capturedPhoto, setCapturedPhoto] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<MealAnalysisResult | null>(null);
  const [photoMimeType, setPhotoMimeType] = useState("image/jpeg");
  const [photoSource, setPhotoSource] = useState<PhotoSource>("camera");

  useEffect(() => {
    void startCamera();
    return () => stopCamera();
    // Camera lifecycle is intentionally tied to page mount/unmount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const analysisMutation = useMutation({
    mutationFn: async () => {
      if (!capturedPhoto) {
        throw new Error("Prenez une photo avant de lancer l'analyse.");
      }
      return analyzeMealPhoto(capturedPhoto, photoMimeType);
    },
    onSuccess: (result) => setAnalysis(result)
  });
  const configQuery = useQuery({
    queryKey: ["meal-analysis-config"],
    queryFn: getMealAnalysisConfig
  });

  async function startCamera() {
    setCameraError(null);
    setCameraState("loading");

    if (typeof window === "undefined") {
      return;
    }

    const isLocalhost = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
    if (!window.isSecureContext && !isLocalhost) {
      setCameraState("error");
      setCameraError("La camera exige un contexte securise (HTTPS ou localhost).");
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraState("error");
      setCameraError("Ce navigateur ne supporte pas l'acces a la camera ou la page n'est pas servie dans un contexte compatible.");
      return;
    }

    stopCamera();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false
      });

      streamRef.current = stream;

      if (!videoRef.current) {
        throw new Error("Le lecteur video n'est pas encore pret.");
      }

      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setCameraState("ready");
    } catch (error) {
      setCameraState("error");
      setCameraError(formatCameraError(error));
    }
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }

  function capturePhoto() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) {
      return;
    }

    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;
    canvas.width = width;
    canvas.height = height;

    const context = canvas.getContext("2d");
    if (!context) {
      setCameraError("Impossible de preparer la capture photo.");
      return;
    }

    context.drawImage(video, 0, 0, width, height);
    const mime = "image/jpeg";
    const dataUrl = canvas.toDataURL(mime, 0.92);
    setPhotoMimeType(mime);
    setCapturedPhoto(dataUrl);
    setPhotoSource("camera");
    setAnalysis(null);
    analysisMutation.reset();
  }

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  function importPhoto(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    if (!file.type.startsWith("image/")) {
      setCameraError("Le fichier selectionne n'est pas une image.");
      setCameraState((current) => (current === "ready" ? current : "error"));
      event.target.value = "";
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : null;
      if (!result) {
        setCameraError("Impossible de lire cette image.");
        setCameraState((current) => (current === "ready" ? current : "error"));
        return;
      }
      setCapturedPhoto(result);
      setPhotoMimeType(file.type || "image/jpeg");
      setPhotoSource("file");
      setAnalysis(null);
      analysisMutation.reset();
      setCameraError(null);
    };
    reader.onerror = () => {
      setCameraError("La lecture du fichier a echoue.");
      setCameraState((current) => (current === "ready" ? current : "error"));
    };
    reader.readAsDataURL(file);
    event.target.value = "";
  }

  function resetPhoto() {
    setCapturedPhoto(null);
    setAnalysis(null);
    setPhotoSource("camera");
    analysisMutation.reset();
  }

  return (
    <Page title="Analyse photo repas" eyebrow="Camera & IA">
      <div className="callout">
        <strong>{configMessageTitle(configQuery.data, analysis)}</strong>
        <div>{configMessageBody(configQuery.data, analysis)}</div>
      </div>

      <div className="meal-analysis-layout">
        <section className="meal-stage-card">
          <div className="meal-card-head">
            <div>
              <span className="eyebrow">Capture temps reel</span>
              <h2>Cadrez votre plat puis prenez une photo</h2>
            </div>
            <StatusBadge value={cameraState === "ready" ? "ACTIF" : cameraState === "loading" ? "Preparation" : "Erreur"} />
          </div>

          <div className="meal-video-shell">
            <video ref={videoRef} className={`meal-video${cameraState === "ready" ? "" : " meal-video-hidden"}`} autoPlay playsInline muted />
            {cameraState === "loading" ? (
              <div className="meal-video-status">
                <LoadingState label="Activation de la camera..." />
              </div>
            ) : null}
            {cameraState === "error" ? (
              <div className="meal-video-status">
                <div className="meal-inline-error">
                  <strong>Camera indisponible</strong>
                  <span>{cameraError || "Impossible d'activer la camera."}</span>
                </div>
              </div>
            ) : null}
            <div className="meal-video-overlay">
              <span>{cameraState === "ready" ? "Alignez le plat dans le cadre" : "Flux camera en attente"}</span>
            </div>
          </div>

          <div className="meal-actions">
            <Button variant="secondary" onClick={() => void startCamera()}>
              <RefreshCcw size={16} />
              Relancer la camera
            </Button>
            <Button onClick={capturePhoto} disabled={cameraState !== "ready"}>
              <Camera size={16} />
              Prendre une photo
            </Button>
            <Button variant="secondary" onClick={openFilePicker}>
              <ImagePlus size={16} />
              Importer une image
            </Button>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="meal-file-input"
            onChange={importPhoto}
          />

          <div className="callout">
            <strong>Aide</strong>
            <div>Si la camera ne s'ouvre pas, verifiez l'autorisation camera du navigateur ou importez une image.</div>
          </div>

          <canvas ref={canvasRef} hidden />
        </section>

        <aside className="meal-side-stack">
          <section className="meal-preview-card">
            <div className="meal-card-head">
              <div>
                <span className="eyebrow">Apercu</span>
                <h2>Photo capturee</h2>
              </div>
              {capturedPhoto ? <StatusBadge value={photoSource === "file" ? "Image importee" : "Pret"} /> : null}
            </div>

            {capturedPhoto ? (
              <div className="meal-preview-stack">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={capturedPhoto} alt="Photo du plat capturee" className="meal-preview-image" />
                <div className="muted">Source : {photoSource === "file" ? "import fichier" : "capture camera"}</div>
                <div className="meal-actions">
                  <Button variant="secondary" onClick={resetPhoto}>
                    <RefreshCcw size={16} />
                    Nouvelle photo
                  </Button>
                  <Button onClick={() => analysisMutation.mutate()} disabled={analysisMutation.isPending}>
                    <ScanSearch size={16} />
                    {analysisMutation.isPending ? "Analyse..." : "Analyser le plat"}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="meal-empty-panel">
                <Camera size={18} />
                <span>Une capture apparaitra ici.</span>
              </div>
            )}
          </section>

          <section className="meal-guide-card">
            <div className="meal-card-head">
              <div>
                <span className="eyebrow">Conseils</span>
                <h2>Pour une meilleure estimation</h2>
              </div>
            </div>
            <ul className="meal-guide-list">
              <li>Cadrez le plat entier si possible.</li>
              <li>Evitez les contre-jours et les reflets forts.</li>
              <li>Gardez une distance stable pour aider l'estimation des portions.</li>
              <li>Si l'IA hesite, une portion standard est indiquee clairement.</li>
            </ul>
          </section>
        </aside>
      </div>

      {analysisMutation.isError ? (
        <div className="meal-inline-error">
          <strong>Analyse impossible</strong>
          <span>{analysisMutation.error.message}</span>
          {capturedPhoto ? (
            <div className="meal-actions">
              <Button variant="secondary" onClick={() => analysisMutation.mutate()}>
                Reessayer l'analyse
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}

      {analysisMutation.isPending ? <LoadingState label="Analyse IA du plat en cours..." /> : null}

      {analysis ? (
        <section className="meal-results-section">
          <div className="meal-results-hero">
            <div className="meal-results-main">
              <span className="eyebrow">Resultat structure</span>
              <h2>{analysis.plat_detecte}</h2>
              <p>{analysis.commentaire}</p>
            </div>
            <div className="meal-badge-stack">
              <StatusBadge value={`${Math.round(analysis.confidence * 100)}% confiance`} />
              <StatusBadge value={analysis.source_analyse.replace("+", " + ")} />
              <StatusBadge value={analysis.mode === "external" ? "Gemini Vision" : "Demo"} />
            </div>
          </div>

          <div className="metric-grid meal-metrics-grid">
            <MetricCard label="Calories estimees" value={formatNumber(analysis.calories_estimees, " kcal")} icon={UtensilsCrossed} />
            <MetricCard label="Proteines" value={formatNumber(analysis.macronutriments.proteines_g, " g")} icon={Sparkles} />
            <MetricCard label="Glucides" value={formatNumber(analysis.macronutriments.glucides_g, " g")} icon={Sparkles} />
            <MetricCard label="Lipides" value={formatNumber(analysis.macronutriments.lipides_g, " g")} icon={Sparkles} />
          </div>

          <div className="meal-results-grid">
            <article className="chart-card">
              <div className="meal-card-head">
                <div>
                  <span className="eyebrow">Aliments visibles</span>
                  <h2>Ingredients detectes</h2>
                </div>
              </div>
              <div className="meal-pill-list">
                {analysis.aliments_detectes.map((food, index) => (
                  <div key={`${food.nom}-${index}`} className="meal-pill-card">
                    <strong>{food.nom}</strong>
                    <span>{confidenceLabel(food.confidence)}</span>
                    <small>Label source : {food.label_source}</small>
                    {food.matched_aliment_nom ? <small>Base locale : {food.matched_aliment_nom} #{food.matched_aliment_id}</small> : <small>Aucune correspondance base locale</small>}
                    {food.portion_estimee ? <small>Portion : {food.portion_estimee}</small> : null}
                    {food.calories_kcal !== undefined && food.calories_kcal !== null ? (
                      <small>
                        {formatNumber(food.calories_kcal, " kcal")} · P {formatNumber(food.proteines_g, " g")} · G {formatNumber(food.glucides_g, " g")} · L {formatNumber(food.lipides_g, " g")}
                      </small>
                    ) : null}
                    {food.details ? <small>{food.details}</small> : null}
                  </div>
                ))}
              </div>
            </article>

            <article className="chart-card">
              <div className="meal-card-head">
                <div>
                  <span className="eyebrow">Portions</span>
                  <h2>Estimations retenues</h2>
                </div>
              </div>
              <div className="meal-result-list">
                {analysis.portions_estimees.map((portion, index) => (
                  <div key={`${portion.nom}-${index}`} className="meal-result-row">
                    <div>
                      <strong>{portion.nom}</strong>
                      <span>{portion.portion}</span>
                    </div>
                    <span>{formatNumber(portion.grammes_estimes, " g")}</span>
                  </div>
                ))}
              </div>
            </article>

            <article className="chart-card">
              <div className="meal-card-head">
                <div>
                  <span className="eyebrow">Hypotheses</span>
                  <h2>Lecture intelligente</h2>
                </div>
              </div>
              <div className="meal-result-list">
                {analysis.hypotheses.length ? analysis.hypotheses.map((item, index) => (
                  <div key={`${item}-${index}`} className="meal-result-row meal-result-row-block">
                    <strong>Hypothese {index + 1}</strong>
                    <small>{item}</small>
                  </div>
                )) : <div className="muted">Aucune hypothese additionnelle.</div>}
              </div>
            </article>

            <article className="chart-card">
              <div className="meal-card-head">
                <div>
                  <span className="eyebrow">Limites</span>
                  <h2>Ce qui reste estimatif</h2>
                </div>
              </div>
              <ul className="meal-guide-list">
                {analysis.limites_estimation.map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            </article>

          </div>
        </section>
      ) : (
        <section className="chart-card meal-results-placeholder">
          <div className="meal-card-head">
            <div>
              <span className="eyebrow">Resultats</span>
              <h2>Le rapport apparaitra ici</h2>
            </div>
          </div>
          <div className="meal-empty-panel">
            <ScanSearch size={18} />
            <span>Prenez une photo puis lancez l'analyse pour obtenir le detail nutritionnel.</span>
          </div>
        </section>
      )}
    </Page>
  );
}

function confidenceLabel(value?: number | null) {
  if (value === undefined || value === null) return "Confiance non renseignee";
  return `${Math.round(value * 100)}% confiance`;
}

function configMessageTitle(
  config?: { external_ai_enabled: boolean; huggingface_configured: boolean; vision_model: string; force_mock: boolean } | null,
  analysis?: MealAnalysisResult | null
) {
  if (!config && !analysis) {
    return "Configuration IA";
  }
  if (analysis?.mode === "external") {
    return "Analyse Gemini Vision active";
  }
  if (config?.external_ai_enabled && config?.huggingface_configured && !config.force_mock) {
    return "IA prete";
  }
  return "Mode demonstration";
}

function configMessageBody(
  config?: { external_ai_enabled: boolean; huggingface_configured: boolean; vision_model: string; force_mock: boolean } | null,
  analysis?: MealAnalysisResult | null
) {
  if (!config && !analysis) {
    return "Verification de la configuration Hugging Face...";
  }
  if (analysis?.mode === "external") {
    return "Analyse Gemini Vision active — aliments detectes avec macros estimees.";
  }
  if (config?.external_ai_enabled && config?.huggingface_configured && !config.force_mock) {
    return "IA configuree. Lancez une analyse pour utiliser la reconnaissance reelle.";
  }
  return "Mode demonstration : configurez GEMINI_API_KEY pour activer la reconnaissance reelle.";
}

function formatCameraError(error: unknown) {
  if (error instanceof DOMException) {
    if (error.name === "NotAllowedError" || error.name === "SecurityError") {
      return "Acces a la camera refuse. Autorisez la camera dans le navigateur puis relancez-la.";
    }
    if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
      return "Aucune camera disponible n'a ete detectee sur cet appareil.";
    }
    if (error.name === "NotReadableError" || error.name === "TrackStartError") {
      return "La camera semble deja utilisee par une autre application ou inaccessible.";
    }
    if (error.name === "OverconstrainedError") {
      return "Les parametres video demandes ne sont pas supportes par la camera disponible.";
    }
    if (error.name === "AbortError") {
      return "Le demarrage de la camera a ete interrompu. Reessayez.";
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Impossible d'activer la camera.";
}
