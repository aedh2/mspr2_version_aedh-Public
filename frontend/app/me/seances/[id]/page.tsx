"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, Dumbbell, Flame, Plus, Repeat, Timer, Weight } from "lucide-react";
import { BarSeries } from "@/src/components/charts/BarSeries";
import { Button } from "@/src/components/ui/button";
import { ChartCard } from "@/src/components/ui/cards";
import { DataTable, type Column } from "@/src/components/ui/data-table";
import { Field, Input, Select, Textarea } from "@/src/components/ui/forms";
import { Modal } from "@/src/components/ui/modal";
import { EmptyState, ErrorState, LoadingState } from "@/src/components/ui/states";
import { useSeance, useSeanceExercices } from "@/src/features/seances/hooks";
import { apiList, apiRequest } from "@/src/lib/api";
import { cleanPayload, SEANCE_EXERCICE_FIELDS } from "@/src/lib/payload";
import { formatDate, formatNumber } from "@/src/lib/format";
import type { Exercice, SeanceExercice } from "@/src/types/domain";

export default function Page() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [addingEx, setAddingEx] = useState(false);
  const seance = useSeance(id);
  const exercices = useSeanceExercices(id);

  if (seance.isLoading) return <LoadingState label="Chargement de la seance..." />;
  if (seance.isError) return <ErrorState message={seance.error.message} onRetry={() => seance.refetch()} />;

  const data = seance.data;
  const rows = exercices.data || [];
  const totalRepetitions = rows.reduce((sum, row) => sum + (row.series_nb || 0) * (row.repetitions_nb || 0), 0);
  const totalVolume = rows.reduce((sum, row) => sum + (row.series_nb || 0) * (row.repetitions_nb || 0) * (row.charge_kg || 0), 0);
  const totalCalories = rows.reduce((sum, row) => sum + (row.calories_brulees_estimees || 0), 0);

  const columns: Column<SeanceExercice>[] = [
    { key: "ordre", header: "#", render: (row) => <span className="tabular">{row.ordre_exercice ?? "—"}</span> },
    {
      key: "exercice",
      header: "Exercice",
      render: (row) => (
        <div style={{ display: "grid", gap: 2 }}>
          <strong style={{ fontFamily: "var(--font-display)" }}>{row.exercice.nom}</strong>
          <span className="muted" style={{ fontSize: 12 }}>
            {[row.exercice.body_part_principale, row.exercice.equipement_principal].filter(Boolean).join(" · ") || "—"}
          </span>
        </div>
      )
    },
    { key: "series", header: "Series × Rep", align: "right", render: (row) => <span className="tabular">{row.series_nb ?? "—"} × {row.repetitions_nb ?? "—"}</span> },
    { key: "charge", header: "Charge", align: "right", render: (row) => formatNumber(row.charge_kg, " kg") },
    { key: "duree", header: "Duree", align: "right", render: (row) => formatNumber(row.duree_min, " min") },
    { key: "calories", header: "Calories", align: "right", render: (row) => formatNumber(row.calories_brulees_estimees, " kcal") },
    { key: "commentaire", header: "Commentaire", render: (row) => row.commentaire || "—" }
  ];

  return (
    <section className="page-section">
      <Link href="/me/seances" className="back-link">
        <ArrowLeft size={14} /> Retour aux seances
      </Link>
      <header className="detail-hero">
        <span className="eyebrow">Seance · {formatDate(data?.date_seance)}</span>
        <h1><em>{data?.type_entrainement || "Entrainement"}</em></h1>
        <p className="lede">
          {data?.niveau_experience ? `Niveau ${data.niveau_experience.toLowerCase()}. ` : ""}
          {data?.commentaire || "Suivi detaille des exercices lies a cette seance."}
        </p>
        <div className="hero-meta">
          <div className="kv"><span>Duree</span><strong>{formatNumber(data?.duree_seance_min, " min")}</strong></div>
          <div className="kv"><span>Calories</span><strong>{formatNumber(data?.calories_brulees_total, " kcal")}</strong></div>
          <div className="kv"><span>Hydratation</span><strong>{formatNumber(data?.eau_l, " L")}</strong></div>
          <div className="kv"><span>Exercices</span><strong>{rows.length}</strong></div>
        </div>
      </header>

      <div className="kv-grid">
        <div className="kv"><span className="label">Volume total</span><span className="value">{formatNumber(totalVolume, " kg")}</span><span className="hint">series × repetitions × charge</span></div>
        <div className="kv"><span className="label">Repetitions</span><span className="value">{formatNumber(totalRepetitions)}</span><span className="hint">cumulees</span></div>
        <div className="kv"><span className="label">Calories estimees</span><span className="value">{formatNumber(totalCalories, " kcal")}</span><span className="hint">par exercice</span></div>
        <div className="kv"><span className="label">Frequence</span><span className="value">{formatNumber(data?.frequence_entrainement_j_sem)}</span><span className="hint">jours / semaine</span></div>
      </div>

      {rows.length > 0 ? (
        <div className="chart-grid">
          <ChartCard title="Calories par exercice" expandable data={rows.map((r) => ({ nom: r.exercice.nom, kcal: r.calories_brulees_estimees ?? 0 }))}>
            <BarSeries data={rows.map((r) => ({ nom: r.exercice.nom, kcal: r.calories_brulees_estimees ?? 0 }))} xKey="nom" series={[{ key: "kcal", label: "Calories", color: "#dc2626" }]} />
          </ChartCard>
          <ChartCard title="Duree par exercice" expandable data={rows.map((r) => ({ nom: r.exercice.nom, min: r.duree_min ?? 0 }))}>
            <BarSeries data={rows.map((r) => ({ nom: r.exercice.nom, min: r.duree_min ?? 0 }))} xKey="nom" series={[{ key: "min", label: "Duree (min)", color: "#2563eb" }]} />
          </ChartCard>
        </div>
      ) : null}

      <div className="section-rule" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3 style={{ display: "inline" }}>Exercices lies</h3> <small>{rows.length} ligne{rows.length > 1 ? "s" : ""}</small>
        </div>
        <Button onClick={() => setAddingEx(true)}><Plus size={16} /> Ajouter exercice</Button>
      </div>

      {exercices.isLoading ? <LoadingState /> : null}
      {exercices.isError ? <ErrorState message={exercices.error.message} onRetry={() => exercices.refetch()} /> : null}
      {!exercices.isLoading && !exercices.isError ? (
        rows.length ? (
          <DataTable rows={rows} columns={columns} getRowKey={(row) => row.seance_exercice_id} />
        ) : (
          <EmptyState label="Aucun exercice enregistre sur cette seance." />
        )
      ) : null}

      <div style={{ display: "flex", gap: 16, color: "var(--muted)", fontSize: 12 }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Dumbbell size={13} /> series</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Repeat size={13} /> repetitions</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Weight size={13} /> charge</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Timer size={13} /> duree</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Flame size={13} /> calories</span>
      </div>

      <AddExerciseModal open={addingEx} onClose={() => setAddingEx(false)} seanceId={id || ""} />
    </section>
  );
}

function AddExerciseModal({ open, onClose, seanceId }: { open: boolean; onClose: () => void; seanceId: string }) {
  const client = useQueryClient();
  const [values, setValues] = useState({
    exercice_id: "",
    ordre_exercice: "",
    series_nb: "",
    repetitions_nb: "",
    charge_kg: "",
    duree_min: "",
    calories_brulees_estimees: "",
    commentaire: ""
  });
  const exercices = useQuery({
    queryKey: ["/api/exercices", "options"],
    queryFn: () => apiList<Exercice>("/api/exercices", { query: { page_size: 100 } }),
    enabled: open
  });
  const mutation = useMutation({
    mutationFn: () =>
      apiRequest(`/api/me/seances/${seanceId}/exercices`, {
        method: "POST",
        body: cleanPayload(values, SEANCE_EXERCICE_FIELDS)
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["me-seance-exercices", String(seanceId)] });
      client.invalidateQueries({ queryKey: ["me-seance", String(seanceId)] });
      setValues({
        exercice_id: "",
        ordre_exercice: "",
        series_nb: "",
        repetitions_nb: "",
        charge_kg: "",
        duree_min: "",
        calories_brulees_estimees: "",
        commentaire: ""
      });
      onClose();
    }
  });

  return (
    <Modal title="Ajouter un exercice" open={open} onClose={onClose}>
      <form className="form-stack" onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
        <Field label="Exercice">
          <Select value={values.exercice_id} onChange={(event) => setValues((state) => ({ ...state, exercice_id: event.target.value }))} required>
            <option value="">{exercices.isLoading ? "Chargement..." : "Selectionner un exercice"}</option>
            {(exercices.data?.data || []).map((exercice) => (
              <option key={exercice.exercice_id} value={exercice.exercice_id}>
                {exercice.nom} {exercice.muscle_cible_principal ? `- ${exercice.muscle_cible_principal}` : ""}
              </option>
            ))}
          </Select>
        </Field>
        <div className="profile-form-grid">
          <Field label="Ordre"><Input type="number" value={values.ordre_exercice} onChange={(event) => setValues((state) => ({ ...state, ordre_exercice: event.target.value }))} /></Field>
          <Field label="Series"><Input type="number" value={values.series_nb} onChange={(event) => setValues((state) => ({ ...state, series_nb: event.target.value }))} /></Field>
          <Field label="Repetitions"><Input type="number" value={values.repetitions_nb} onChange={(event) => setValues((state) => ({ ...state, repetitions_nb: event.target.value }))} /></Field>
          <Field label="Charge (kg)"><Input type="number" step="0.1" value={values.charge_kg} onChange={(event) => setValues((state) => ({ ...state, charge_kg: event.target.value }))} /></Field>
          <Field label="Duree (min)"><Input type="number" step="0.1" value={values.duree_min} onChange={(event) => setValues((state) => ({ ...state, duree_min: event.target.value }))} /></Field>
          <Field label="Calories"><Input type="number" step="0.1" value={values.calories_brulees_estimees} onChange={(event) => setValues((state) => ({ ...state, calories_brulees_estimees: event.target.value }))} /></Field>
        </div>
        <Field label="Commentaire"><Textarea rows={3} value={values.commentaire} onChange={(event) => setValues((state) => ({ ...state, commentaire: event.target.value }))} /></Field>
        {!exercices.isLoading && !(exercices.data?.data || []).length ? <div className="form-error">Aucun exercice charge depuis la base.</div> : null}
        {mutation.isError ? <div className="form-error">{mutation.error.message}</div> : null}
        <div className="form-actions">
          <Button variant="secondary" type="button" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? "Ajout..." : "Ajouter"}</Button>
        </div>
      </form>
    </Modal>
  );
}
