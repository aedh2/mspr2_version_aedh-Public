"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Dumbbell, Eye, Plus } from "lucide-react";
import { StatusBadge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { Field, Input, Select } from "@/src/components/ui/forms";
import { Modal } from "@/src/components/ui/modal";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { useDebouncedValue } from "@/src/hooks/use-debounced-value";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { apiRequest } from "@/src/lib/api";
import type { Exercice, ExerciceFilters } from "@/src/types/domain";
import { cleanPayload, EXERCICE_FIELDS } from "@/src/lib/payload";
import { Page } from "./_shared";

const schema = z.object({
  nom: z.string().min(1),
  body_part_principale: z.string().optional(),
  muscle_cible_principal: z.string().optional(),
  equipement_principal: z.string().optional(),
  external_id: z.string().optional(),
  gif_180_path: z.string().optional(),
  gif_360_path: z.string().optional(),
  gif_720_path: z.string().optional(),
  gif_1080_path: z.string().optional()
});
type Form = z.infer<typeof schema>;

export function AdminExercicesPage() {
  const [search, setSearch] = useState("");
  const [bodyPart, setBodyPart] = useState("");
  const [muscle, setMuscle] = useState("");
  const [equipment, setEquipment] = useState("");
  const debounced = useDebouncedValue(search, 300);
  const queryParams = useMemo(
    () => ({ q: debounced, body_part_principale: bodyPart, muscle_cible_principal: muscle, equipement_principal: equipment }),
    [debounced, bodyPart, muscle, equipment]
  );
  const query = usePagedApi<Exercice>("/api/exercices", queryParams, 30);
  const filters = useQuery({
    queryKey: ["/api/exercices/filters"],
    queryFn: () => apiRequest<ExerciceFilters>("/api/exercices/filters")
  });
  const rows = query.data?.data || [];
  const [editing, setEditing] = useState<Exercice | null>(null);
  const [viewing, setViewing] = useState<Exercice | null>(null);

  useEffect(() => {
    query.setPage(1);
  }, [debounced, bodyPart, muscle, equipment]);

  return (
    <Page
      title="Catalogue exercices"
      eyebrow="Referentiels admin"
      actions={<Button onClick={() => setEditing({} as Exercice)}><Plus size={16} /> Creer</Button>}
    >
      <div className="filter-bar">
        <Input placeholder="Rechercher..." value={search} onChange={(event) => setSearch(event.target.value)} />
        <Select value={bodyPart} onChange={(event) => setBodyPart(event.target.value)}>
          <option value="">Toutes zones</option>
          {(filters.data?.body_parts || []).map((item) => <option key={item} value={item}>{item}</option>)}
        </Select>
        <Select value={muscle} onChange={(event) => setMuscle(event.target.value)}>
          <option value="">Tous muscles</option>
          {(filters.data?.target_muscles || []).map((item) => <option key={item} value={item}>{item}</option>)}
        </Select>
        <Select value={equipment} onChange={(event) => setEquipment(event.target.value)}>
          <option value="">Tous equipements</option>
          {(filters.data?.equipements || []).map((item) => <option key={item} value={item}>{item}</option>)}
        </Select>
      </div>
      {query.isLoading ? <LoadingState label="Chargement du catalogue..." /> : null}
      {query.isError ? <ErrorState message={query.error.message} onRetry={() => query.refetch()} /> : null}
      {!query.isLoading && !query.isError ? (
        <>
          <div className="exercise-grid">
            {rows.map((row) => (
              <article className="exercise-card" key={row.exercice_id}>
                <button className="exercise-card-button" type="button" onClick={() => setViewing(row)}>
                  {bestGif(row) ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={bestGif(row) || ""} alt={row.nom} />
                  ) : (
                    <div className="exercise-thumb-fallback"><Dumbbell size={28} /></div>
                  )}
                  <span>
                    <strong>{row.nom}</strong>
                    <small>{row.body_part_principale || "Zone inconnue"} · {row.muscle_cible_principal || "Muscle inconnu"}</small>
                  </span>
                </button>
                <div className="exercise-card-meta">
                  {row.equipement_principal ? <StatusBadge value={row.equipement_principal} /> : null}
                  <div className="row-actions">
                    <Button variant="secondary" onClick={() => setViewing(row)}><Eye size={15} /> Voir</Button>
                    <Button variant="secondary" onClick={() => setEditing(row)}>Editer</Button>
                  </div>
                </div>
              </article>
            ))}
          </div>
          <div className="pagination">
            <Button variant="secondary" disabled={query.page <= 1} onClick={() => query.setPage(query.page - 1)}>Precedent</Button>
            <span>Page {query.page} / {query.data?.meta?.totalPages || 1}</span>
            <Button variant="secondary" disabled={query.page >= (query.data?.meta?.totalPages || 1)} onClick={() => query.setPage(query.page + 1)}>Suivant</Button>
          </div>
        </>
      ) : null}
      <ExerciceDetail exercice={viewing} onClose={() => setViewing(null)} onEdit={(exercice) => { setViewing(null); setEditing(exercice); }} />
      <ExerciceModal exercice={editing} onClose={() => setEditing(null)} />
    </Page>
  );
}

function parseJsonList(value?: string | null) {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

function bestGif(exercice: Exercice) {
  return exercice.gif_360_url || exercice.gif_180_url || exercice.gif_720_url || exercice.gif_1080_url || null;
}

function ExerciceDetail({
  exercice,
  onClose,
  onEdit
}: {
  exercice: Exercice | null;
  onClose: () => void;
  onEdit: (exercice: Exercice) => void;
}) {
  const [quality, setQuality] = useState<"180" | "360" | "720" | "1080">("360");
  if (!exercice) {
    return null;
  }
  const gifs = {
    "180": exercice.gif_180_url,
    "360": exercice.gif_360_url,
    "720": exercice.gif_720_url,
    "1080": exercice.gif_1080_url
  };
  const activeGif = gifs[quality] || bestGif(exercice);
  const bodyParts = parseJsonList(exercice.body_parts_json);
  const targets = parseJsonList(exercice.target_muscles_json);
  const secondary = parseJsonList(exercice.secondary_muscles_json);
  const equipments = parseJsonList(exercice.equipments_json);
  const instructions = parseJsonList(exercice.instructions_json);

  return (
    <Modal title="Detail exercice" open={Boolean(exercice)} onClose={onClose}>
      <div className="exercise-detail">
        {activeGif ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={activeGif} alt={exercice.nom} />
        ) : (
          <div className="exercise-thumb-fallback"><Dumbbell size={36} /></div>
        )}
        <div className="tab-bar">
          {Object.entries(gifs).map(([key, url]) => (
            <Button key={key} type="button" variant={quality === key ? "primary" : "secondary"} disabled={!url} onClick={() => setQuality(key as typeof quality)}>
              {key}p
            </Button>
          ))}
        </div>
        <h3>{exercice.nom}</h3>
        <div className="badge-row">
          {[...bodyParts, ...targets, ...secondary, ...equipments]
            .filter(Boolean)
            .slice(0, 10)
            .map((item) => <StatusBadge key={item} value={item} />)}
        </div>
        <ol className="instruction-list">
          {instructions.length ? instructions.map((item, index) => <li key={`${item}-${index}`}>{item}</li>) : <li>Aucune instruction detaillee.</li>}
        </ol>
        <div className="form-actions">
          <Button variant="secondary" onClick={onClose}>Fermer</Button>
          <Button onClick={() => onEdit(exercice)}>Editer</Button>
        </div>
      </div>
    </Modal>
  );
}

function ExerciceModal({ exercice, onClose }: { exercice: Exercice | null; onClose: () => void }) {
  const client = useQueryClient();
  const isNew = exercice && !exercice.exercice_id;
  const form = useForm<Form>({
    resolver: zodResolver(schema),
    values: {
      nom: exercice?.nom || "",
      body_part_principale: exercice?.body_part_principale || "",
      muscle_cible_principal: exercice?.muscle_cible_principal || "",
      equipement_principal: exercice?.equipement_principal || "",
      external_id: exercice?.external_id || "",
      gif_180_path: exercice?.gif_180_path || "",
      gif_360_path: exercice?.gif_360_path || "",
      gif_720_path: exercice?.gif_720_path || "",
      gif_1080_path: exercice?.gif_1080_path || ""
    }
  });
  const mutation = useMutation({
    mutationFn: (values: Form) =>
      apiRequest(`/api/exercices${isNew ? "" : `/${exercice?.exercice_id}`}`, {
        method: isNew ? "POST" : "PATCH",
        body: cleanPayload(values, EXERCICE_FIELDS)
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["/api/exercices"] });
      onClose();
    }
  });
  return (
    <Modal title={isNew ? "Creer un exercice" : "Modifier exercice"} open={Boolean(exercice)} onClose={onClose}>
      <form className="form-stack" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Nom"><Input {...form.register("nom")} /></Field>
        <Field label="Body part principal"><Input {...form.register("body_part_principale")} /></Field>
        <Field label="Muscle cible"><Input {...form.register("muscle_cible_principal")} /></Field>
        <Field label="Equipement"><Input {...form.register("equipement_principal")} /></Field>
        <Field label="External ID"><Input {...form.register("external_id")} /></Field>
        <Field label="GIF 180 path"><Input {...form.register("gif_180_path")} /></Field>
        <Field label="GIF 360 path"><Input {...form.register("gif_360_path")} /></Field>
        <Field label="GIF 720 path"><Input {...form.register("gif_720_path")} /></Field>
        <Field label="GIF 1080 path"><Input {...form.register("gif_1080_path")} /></Field>
        {mutation.isError ? <div className="form-error">{mutation.error?.message || "Une erreur est survenue."}</div> : null}
        <div className="form-actions">
          <Button variant="secondary" type="button" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={mutation.isPending}>Enregistrer</Button>
        </div>
      </form>
    </Modal>
  );
}
