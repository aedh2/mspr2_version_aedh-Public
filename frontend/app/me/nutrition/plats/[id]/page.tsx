"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { BarSeries } from "@/src/components/charts/BarSeries";
import { Button } from "@/src/components/ui/button";
import { ChartCard } from "@/src/components/ui/cards";
import { DataTable, type Column } from "@/src/components/ui/data-table";
import { Field, Input, Select, Textarea } from "@/src/components/ui/forms";
import { Modal } from "@/src/components/ui/modal";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { usePlat, usePlatLignes } from "@/src/features/nutrition/hooks";
import { apiList, apiRequest } from "@/src/lib/api";
import { cleanPayload, JOURNAL_ALIMENTAIRE_FIELDS } from "@/src/lib/payload";
import { formatDate, formatNumber } from "@/src/lib/format";
import type { Aliment, PlatLigne } from "@/src/types/domain";

export default function Page() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [adding, setAdding] = useState(false);
  const plat = usePlat(id);
  const lignes = usePlatLignes(id);

  if (plat.isLoading) return <LoadingState label="Chargement du plat..." />;
  if (plat.isError) return <ErrorState message={plat.error.message} onRetry={() => plat.refetch()} />;

  const data = plat.data;
  const rows = lignes.data || [];
  const sommeLignes = data?.somme_lignes_kcal ?? rows.reduce((sum, row) => sum + (row.calories_kcal || 0), 0);
  const totales = data?.calories_totales_kcal || 0;
  const ecart = totales - (sommeLignes || 0);
  const incoherent = data?.coherence_calories === false || Math.abs(ecart) > 5;

  const columns: Column<PlatLigne>[] = [
    {
      key: "aliment",
      header: "Aliment",
      render: (row) => (
        <div style={{ display: "grid", gap: 2 }}>
          <strong style={{ fontFamily: "var(--font-display)" }}>{row.aliment?.nom || row.aliment_nom_libre || `Aliment #${row.aliment_id ?? "—"}`}</strong>
          {row.aliment?.categorie ? <span className="muted" style={{ fontSize: 12 }}>{row.aliment.categorie}</span> : null}
        </div>
      )
    },
    { key: "quantite", header: "Quantite", align: "right", render: (row) => `${formatNumber(row.quantite)} ${row.unite_quantite || ""}`.trim() },
    { key: "kcal", header: "Calories", align: "right", render: (row) => formatNumber(row.calories_kcal, " kcal") },
    { key: "prot", header: "Proteines", align: "right", render: (row) => formatNumber(scaleMacro(row.aliment?.proteines_g, row.quantite, row.unite_quantite), " g") },
    { key: "gluc", header: "Glucides", align: "right", render: (row) => formatNumber(scaleMacro(row.aliment?.glucides_g, row.quantite, row.unite_quantite), " g") },
    { key: "lip", header: "Lipides", align: "right", render: (row) => formatNumber(scaleMacro(row.aliment?.lipides_g, row.quantite, row.unite_quantite), " g") }
  ];

  return (
    <section className="page-section">
      <Link href="/me/nutrition" className="back-link">
        <ArrowLeft size={14} /> Retour aux plats
      </Link>

      <header className="detail-hero">
        <span className="eyebrow">{data?.type_repas || "Repas"} · {formatDate(data?.consomme_le)}</span>
        <h1><em>{data?.nom_plat || `Plat #${data?.plat_id ?? id}`}</em></h1>
        <p className="lede">Detail des lignes alimentaires et controle automatique des calories.</p>
        <div className="hero-meta">
          <div className="kv"><span>Calories declarees</span><strong>{formatNumber(totales, " kcal")}</strong></div>
          <div className="kv"><span>Somme lignes</span><strong>{formatNumber(sommeLignes, " kcal")}</strong></div>
          <div className="kv"><span>Ecart</span><strong style={{ color: incoherent ? "var(--accent)" : undefined }}>{ecart >= 0 ? "+" : ""}{formatNumber(ecart, " kcal")}</strong></div>
          <div className="kv"><span>Lignes</span><strong>{rows.length}</strong></div>
        </div>
      </header>

      {incoherent ? (
        <div className="callout">
          <strong>Incoherence detectee.</strong> Le total du plat differe de la somme des lignes de plus de 5 kcal.
        </div>
      ) : null}

      {rows.length > 0 ? (
        <ChartCard title="Calories par aliment" expandable data={rows.map((row) => ({ nom: row.aliment?.nom || row.aliment_nom_libre || `#${row.aliment_id ?? "?"}`, kcal: row.calories_kcal ?? 0 }))}>
          <BarSeries data={rows.map((row) => ({ nom: row.aliment?.nom || row.aliment_nom_libre || `#${row.aliment_id ?? "?"}`, kcal: row.calories_kcal ?? 0 }))} xKey="nom" series={[{ key: "kcal", label: "Calories", color: "#0284c7" }]} />
        </ChartCard>
      ) : null}

      <div className="section-rule">
        <h3>Lignes alimentaires</h3>
        <Button onClick={() => setAdding(true)}><Plus size={16} /> Ajouter</Button>
      </div>

      {lignes.isLoading ? <LoadingState /> : null}
      {lignes.isError ? <ErrorState message={lignes.error.message} onRetry={() => lignes.refetch()} /> : null}
      {!lignes.isLoading && !lignes.isError ? (
        <DataTable rows={rows} columns={columns} getRowKey={(row) => row.journal_id} emptyLabel="Aucune ligne alimentaire pour ce plat." />
      ) : null}

      <AddFoodLineModal open={adding} onClose={() => setAdding(false)} platId={id || ""} />
    </section>
  );
}

function scaleMacro(value?: number | null, quantity?: number | null, unit?: string | null) {
  if (value == null || quantity == null) return value ?? null;
  const normalized = (unit || "").toLowerCase();
  if (normalized === "g" || normalized === "ml") return round2(value * (quantity / 100));
  if (normalized === "kg" || normalized === "l") return round2(value * quantity * 10);
  return round2(value * quantity);
}

function round2(value: number) {
  return Math.round(value * 100) / 100;
}

function AddFoodLineModal({ open, onClose, platId }: { open: boolean; onClose: () => void; platId: string }) {
  const client = useQueryClient();
  const [mode, setMode] = useState<"catalogue" | "libre">("catalogue");
  const [values, setValues] = useState({
    aliment_id: "",
    aliment_nom_libre: "",
    quantite: "100",
    unite_quantite: "g",
    calories_kcal: "",
    eau_ml: "",
    commentaire: ""
  });
  const aliments = useQuery({
    queryKey: ["/api/aliments", "options"],
    queryFn: () => apiList<Aliment>("/api/aliments", { query: { page_size: 100 } }),
    enabled: open
  });
  const selectedAliment = useMemo(
    () => (aliments.data?.data || []).find((aliment) => String(aliment.aliment_id) === values.aliment_id) || null,
    [aliments.data?.data, values.aliment_id]
  );
  const derivedCalories = useMemo(() => {
    if (!selectedAliment) return null;
    const quantity = Number(values.quantite || 0);
    if (!Number.isFinite(quantity) || quantity <= 0) return null;
    const unit = values.unite_quantite.toLowerCase();
    const factor = unit === "g" || unit === "ml" ? quantity / 100 : unit === "kg" || unit === "l" ? quantity * 10 : quantity;
    return round2((selectedAliment.calories_kcal || 0) * factor);
  }, [selectedAliment, values.quantite, values.unite_quantite]);
  const mutation = useMutation({
    mutationFn: () => {
      const payload = mode === "catalogue"
        ? {
            aliment_id: values.aliment_id,
            quantite: values.quantite,
            unite_quantite: values.unite_quantite,
            calories_kcal: derivedCalories,
            eau_ml: values.eau_ml
          }
        : {
            aliment_nom_libre: values.aliment_nom_libre,
            quantite: values.quantite,
            unite_quantite: values.unite_quantite,
            calories_kcal: values.calories_kcal,
            eau_ml: values.eau_ml
          };
      return apiRequest(`/api/me/plats/${platId}/lignes`, {
        method: "POST",
        body: cleanPayload(payload, JOURNAL_ALIMENTAIRE_FIELDS)
      });
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["me-plat", String(platId)] });
      client.invalidateQueries({ queryKey: ["me-plat-lignes", String(platId)] });
      client.invalidateQueries({ queryKey: ["/api/me/plats"] });
      client.invalidateQueries({ queryKey: ["/api/me/journal-alimentaire"] });
      onClose();
    }
  });

  return (
    <Modal title="Ajouter un aliment" open={open} onClose={onClose}>
      <form className="form-stack" onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
        <div className="toggle-row">
          <Button variant={mode === "catalogue" ? "primary" : "secondary"} onClick={() => setMode("catalogue")} type="button">Depuis la BDD</Button>
          <Button variant={mode === "libre" ? "primary" : "secondary"} onClick={() => setMode("libre")} type="button">Aliment libre</Button>
        </div>
        {mode === "catalogue" ? (
          <Field label="Aliment">
            <Select value={values.aliment_id} onChange={(event) => setValues((state) => ({ ...state, aliment_id: event.target.value }))} required>
              <option value="">{aliments.isLoading ? "Chargement..." : "Selectionner un aliment"}</option>
              {(aliments.data?.data || []).map((aliment) => (
                <option key={aliment.aliment_id} value={aliment.aliment_id}>
                  {aliment.nom} {aliment.calories_kcal != null ? `(${aliment.calories_kcal} kcal)` : ""}
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <Field label="Nom de l'aliment">
            <Input value={values.aliment_nom_libre} onChange={(event) => setValues((state) => ({ ...state, aliment_nom_libre: event.target.value }))} required />
          </Field>
        )}
        <div className="profile-form-grid">
          <Field label="Quantite"><Input type="number" step="0.1" value={values.quantite} onChange={(event) => setValues((state) => ({ ...state, quantite: event.target.value }))} /></Field>
          <Field label="Unite">
            <Select value={values.unite_quantite} onChange={(event) => setValues((state) => ({ ...state, unite_quantite: event.target.value }))}>
              <option value="g">g</option>
              <option value="ml">ml</option>
              <option value="portion">portion</option>
              <option value="piece">piece</option>
            </Select>
          </Field>
          {mode === "libre" ? (
            <>
              <Field label="Calories">
                <Input type="number" step="0.1" value={values.calories_kcal} onChange={(event) => setValues((state) => ({ ...state, calories_kcal: event.target.value }))} required />
              </Field>
              <Field label="Eau (ml)">
                <Input type="number" step="0.1" value={values.eau_ml} onChange={(event) => setValues((state) => ({ ...state, eau_ml: event.target.value }))} />
              </Field>
            </>
          ) : null}
        </div>
        {selectedAliment ? (
          <div className="objective-detail-grid">
            <span><strong>Calories calculees</strong>{formatNumber(derivedCalories, " kcal")}</span>
            <span><strong>Proteines</strong>{formatNumber(scaleMacro(selectedAliment.proteines_g, Number(values.quantite), values.unite_quantite), " g")}</span>
            <span><strong>Glucides</strong>{formatNumber(scaleMacro(selectedAliment.glucides_g, Number(values.quantite), values.unite_quantite), " g")}</span>
            <span><strong>Lipides</strong>{formatNumber(scaleMacro(selectedAliment.lipides_g, Number(values.quantite), values.unite_quantite), " g")}</span>
            <span><strong>Categorie</strong>{selectedAliment.categorie || "—"}</span>
          </div>
        ) : null}
        {!aliments.isLoading && !selectedAliment && mode === "catalogue" && !(aliments.data?.data || []).length ? (
          <div className="form-error">Aucun aliment charge depuis la base.</div>
        ) : null}
        <Field label="Commentaire">
          <Textarea rows={3} value={values.commentaire} onChange={(event) => setValues((state) => ({ ...state, commentaire: event.target.value }))} />
        </Field>
        {mutation.isError ? <div className="form-error">{mutation.error.message}</div> : null}
        <div className="form-actions">
          <Button variant="secondary" type="button" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? "Ajout..." : "Ajouter"}</Button>
        </div>
      </form>
    </Modal>
  );
}
