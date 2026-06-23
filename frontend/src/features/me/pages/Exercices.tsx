"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Modal } from "@/src/components/ui/modal";
import { Pagination } from "@/src/components/ui/pagination";
import { SearchInput, Select } from "@/src/components/ui/forms";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { useExercice, useExerciceFilters } from "@/src/features/exercices/hooks";
import { useDebouncedValue } from "@/src/hooks/use-debounced-value";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import type { Exercice } from "@/src/types/domain";
import { Page } from "./_shared";

function parseJson<T>(value?: string | null): T | null {
  if (!value) return null;
  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}

export function ExercicesPage() {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 300);
  const [bodyPart, setBodyPart] = useState("");
  const [muscle, setMuscle] = useState("");
  const [equipement, setEquipement] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const filters = useExerciceFilters();

  const queryParams = useMemo(() => {
    const params: Record<string, string> = {};
    if (debouncedSearch) params.search = debouncedSearch;
    if (bodyPart) params.body_part_principale = bodyPart;
    if (muscle) params.muscle_cible_principal = muscle;
    if (equipement) params.equipement_principal = equipement;
    return params;
  }, [debouncedSearch, bodyPart, muscle, equipement]);

  const query = usePagedApi<Exercice>("/api/exercices", queryParams, 24);
  useEffect(() => {
    query.setPage(1);
  }, [debouncedSearch, bodyPart, muscle, equipement]);

  const rows = query.data?.data || [];

  return (
    <Page title="Catalogue d'exercices" eyebrow="Bibliotheque">
      <div className="filter-bar">
        <SearchInput label="Rechercher un exercice" placeholder="Rechercher un exercice..." value={search} onChange={(event) => setSearch(event.target.value)} />
        <Select value={bodyPart} onChange={(event) => setBodyPart(event.target.value)} disabled={filters.isLoading}>
          <option value="">{filters.isLoading ? "Chargement..." : "Body part"}</option>
          {(filters.data?.body_parts || []).map((value) => <option key={value} value={value}>{value}</option>)}
        </Select>
        <Select value={muscle} onChange={(event) => setMuscle(event.target.value)} disabled={filters.isLoading}>
          <option value="">{filters.isLoading ? "Chargement..." : "Muscle cible"}</option>
          {(filters.data?.target_muscles || []).map((value) => <option key={value} value={value}>{value}</option>)}
        </Select>
        <Select value={equipement} onChange={(event) => setEquipement(event.target.value)} disabled={filters.isLoading}>
          <option value="">{filters.isLoading ? "Chargement..." : "Equipement"}</option>
          {(filters.data?.equipements || []).map((value) => <option key={value} value={value}>{value}</option>)}
        </Select>
      </div>

      {query.isLoading ? <LoadingState /> : null}
      {query.isError ? <ErrorState message={query.error.message} onRetry={() => query.refetch()} /> : null}

      {!query.isLoading && !query.isError ? (
        <>
          <div className="exercise-grid">
            {rows.map((exercice) => (
              <button key={exercice.exercice_id} type="button" className="exercise-card exercise-card-button" onClick={() => setSelectedId(exercice.exercice_id)}>
                {exercice.gif_360_url || exercice.gif_180_url || exercice.gif_360_path || exercice.gif_180_path ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={exercice.gif_360_url || exercice.gif_180_url || exercice.gif_360_path || exercice.gif_180_path || ""}
                    alt={exercice.nom}
                    loading="lazy"
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  />
                ) : (
                  <div className="exercise-thumb-fallback"><Search size={20} /></div>
                )}
                <div className="exercise-card-meta">
                  <div>
                    <strong>{exercice.nom}</strong>
                    <small className="muted">
                      {[exercice.body_part_principale, exercice.muscle_cible_principal, exercice.equipement_principal].filter(Boolean).join(" · ") || "—"}
                    </small>
                  </div>
                  <span className="row-open-hint">Detail</span>
                </div>
              </button>
            ))}
            {rows.length === 0 ? <div className="muted">Aucun exercice trouve.</div> : null}
          </div>
          <Pagination meta={query.data?.meta} page={query.page} onPageChange={query.setPage} />
        </>
      ) : null}

      <ExerciseDetailModal id={selectedId} onClose={() => setSelectedId(null)} />
    </Page>
  );
}

function ExerciseDetailModal({ id, onClose }: { id: number | null; onClose: () => void }) {
  const exercice = useExercice(id || undefined);
  const [activeVariant, setActiveVariant] = useState<string>("");

  useEffect(() => {
    if (exercice.data) {
      const first =
        exercice.data.gif_360_url ||
        exercice.data.gif_180_url ||
        exercice.data.gif_720_url ||
        exercice.data.gif_1080_url ||
        "";
      setActiveVariant(first);
    }
  }, [exercice.data]);

  const data = exercice.data;
  const instructions = parseJson<string[]>(data?.instructions_json) || [];
  const bodyParts = parseJson<string[]>(data?.body_parts_json) || [];
  const targetMuscles = parseJson<string[]>(data?.target_muscles_json) || [];
  const secondaryMuscles = parseJson<string[]>(data?.secondary_muscles_json) || [];
  const equipements = parseJson<string[]>(data?.equipments_json) || [];
  const variants = [
    { label: "180", value: data?.gif_180_url || data?.gif_180_path || "" },
    { label: "360", value: data?.gif_360_url || data?.gif_360_path || "" },
    { label: "720", value: data?.gif_720_url || data?.gif_720_path || "" },
    { label: "1080", value: data?.gif_1080_url || data?.gif_1080_path || "" }
  ].filter((variant) => variant.value);

  return (
    <Modal title={data?.nom || "Detail exercice"} open={Boolean(id)} onClose={onClose} className="chart-modal">
      {exercice.isLoading ? <LoadingState label="Chargement de l'exercice..." /> : null}
      {exercice.isError ? <ErrorState message={exercice.error.message} onRetry={() => exercice.refetch()} /> : null}
      {data ? (
        <div className="exercise-detail">
          <div className="form-actions" style={{ justifyContent: "flex-start" }}>
            {variants.map((variant) => (
              <button key={variant.label} type="button" className={`button ${activeVariant === variant.value ? "button-primary" : "button-secondary"}`} onClick={() => setActiveVariant(variant.value)}>
                {variant.label}px
              </button>
            ))}
          </div>
          {activeVariant ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={activeVariant} alt={data.nom} />
          ) : (
            <div className="empty-chart">Aucun GIF disponible.</div>
          )}
          <div className="badge-row">
            {[...bodyParts, ...targetMuscles, ...equipements].filter(Boolean).slice(0, 8).map((item) => (
              <span key={item} className="badge badge-neutral">{item}</span>
            ))}
          </div>
          <div className="objective-detail-grid">
            <span><strong>Body parts</strong>{bodyParts.join(", ") || data.body_part_principale || "—"}</span>
            <span><strong>Muscles cibles</strong>{targetMuscles.join(", ") || data.muscle_cible_principal || "—"}</span>
            <span><strong>Muscles secondaires</strong>{secondaryMuscles.join(", ") || "—"}</span>
            <span><strong>Equipements</strong>{equipements.join(", ") || data.equipement_principal || "—"}</span>
          </div>
          <div>
            <strong>Instructions</strong>
            {instructions.length ? (
              <ol className="instruction-list">
                {instructions.map((step, index) => <li key={index}>{step}</li>)}
              </ol>
            ) : (
              <p className="muted">Aucune instruction disponible.</p>
            )}
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
