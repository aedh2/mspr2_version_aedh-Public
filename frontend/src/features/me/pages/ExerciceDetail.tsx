"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { ChartCard } from "@/src/components/ui/cards";
import { Button } from "@/src/components/ui/button";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { useExercice } from "@/src/features/exercices/hooks";

function parseJson<T>(value?: string | null): T | null {
  if (!value) return null;
  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}

export function ExerciceDetailPage({ id }: { id: string }) {
  const exercice = useExercice(id);
  const variants: Array<{ key: keyof typeof gifs; label: string }> = [
    { key: "gif_360_url", label: "360" },
    { key: "gif_180_url", label: "180" },
    { key: "gif_720_url", label: "720" },
    { key: "gif_1080_url", label: "1080" }
  ];

  if (exercice.isLoading) return <LoadingState label="Chargement de l'exercice..." />;
  if (exercice.isError) return <ErrorState message={exercice.error.message} onRetry={() => exercice.refetch()} />;
  const data = exercice.data!;

  // Use URLs first, then fallback to paths, then null
  const gifs: Record<string, string | null | undefined> = {
    gif_180_url: data.gif_180_url || data.gif_180_path,
    gif_180_path: data.gif_180_url || data.gif_180_path,
    gif_360_url: data.gif_360_url || data.gif_360_path,
    gif_360_path: data.gif_360_url || data.gif_360_path,
    gif_720_url: data.gif_720_url || data.gif_720_path,
    gif_720_path: data.gif_720_url || data.gif_720_path,
    gif_1080_url: data.gif_1080_url || data.gif_1080_path,
    gif_1080_path: data.gif_1080_url || data.gif_1080_path
  };
  const availableVariants = variants.filter((v) => gifs[v.key]);
  const [activeVariant, setActiveVariant] = useState<string>(availableVariants[0]?.key ?? "gif_360_url");

  const instructions = parseJson<string[]>(data.instructions_json) || [];
  const bodyParts = parseJson<string[]>(data.body_parts_json) || [];
  const targetMuscles = parseJson<string[]>(data.target_muscles_json) || [];
  const secondaryMuscles = parseJson<string[]>(data.secondary_muscles_json) || [];
  const equipements = parseJson<string[]>(data.equipments_json) || [];

  return (
    <section className="page-section">
      <Link href="/me/exercices" className="back-link">
        <ArrowLeft size={14} /> Retour au catalogue
      </Link>

      <header className="detail-hero">
        <span className="eyebrow">Exercice · #{data.exercice_id}</span>
        <h1><em>{data.nom}</em></h1>
        <div className="hero-meta">
          <div className="kv">
            <span>Body part</span>
            <strong>{data.body_part_principale || "—"}</strong>
          </div>
          <div className="kv">
            <span>Muscle cible</span>
            <strong>{data.muscle_cible_principal || "—"}</strong>
          </div>
          <div className="kv">
            <span>Equipement</span>
            <strong>{data.equipement_principal || "—"}</strong>
          </div>
        </div>
      </header>

      <div className="chart-grid" style={{ gridTemplateColumns: "minmax(0, 360px) minmax(0, 1fr)" }}>
        <ChartCard title="Demonstration">
          {availableVariants.length > 0 ? (
            <div style={{ display: "grid", gap: 10 }}>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {availableVariants.map((v) => (
                  <Button
                    key={v.key}
                    variant={activeVariant === v.key ? "primary" : "secondary"}
                    onClick={() => setActiveVariant(v.key)}
                    type="button"
                  >
                    {v.label}px
                  </Button>
                ))}
              </div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={gifs[activeVariant] || ""}
                alt={data.nom}
                style={{ width: "100%", borderRadius: 8, border: "1px solid var(--rule)", backgroundColor: "var(--surface-2)", minHeight: 200 }}
                loading="lazy"
              />
            </div>
          ) : (
            <div className="muted" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: 200 }}>Aucun GIF disponible.</div>
          )}
        </ChartCard>

        <ChartCard title="Instructions">
          {instructions.length === 0 ? (
            <div className="muted">Aucune instruction fournie.</div>
          ) : (
            <ol style={{ display: "grid", gap: 8, paddingLeft: 18, margin: 0 }}>
              {instructions.map((step, idx) => (
                <li key={idx}>{step}</li>
              ))}
            </ol>
          )}
        </ChartCard>
      </div>

      <div className="chart-grid">
        <ChartCard title="Muscles & equipements">
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 6 }}>
            <li><span className="muted">Body parts :</span> {bodyParts.join(", ") || "—"}</li>
            <li><span className="muted">Muscles cibles :</span> {targetMuscles.join(", ") || "—"}</li>
            <li><span className="muted">Muscles secondaires :</span> {secondaryMuscles.join(", ") || "—"}</li>
            <li><span className="muted">Equipements :</span> {equipements.join(", ") || "—"}</li>
          </ul>
        </ChartCard>
        <ChartCard title="Reference">
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 6 }}>
            <li><span className="muted">External ID :</span> {data.external_id || "—"}</li>
            <li><span className="muted">Source ID :</span> {data.source_id ?? "—"}</li>
          </ul>
        </ChartCard>
      </div>
    </section>
  );
}
