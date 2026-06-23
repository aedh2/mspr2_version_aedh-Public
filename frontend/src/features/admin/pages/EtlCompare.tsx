"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { RotateCcw } from "lucide-react";
import { StatusBadge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { ChartCard } from "@/src/components/ui/cards";
import { DataTable, type Column } from "@/src/components/ui/data-table";
import { Field, Input, Select } from "@/src/components/ui/forms";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { apiRequest } from "@/src/lib/api";
import type { ControleQualite, EtlCompareChange } from "@/src/types/domain";
import { Page } from "./_shared";

type CompareOptions = {
  lots: Array<{ id: number; nom: string }>;
  sources: Array<{ id: number; nom: string }>;
  entites: string[];
  refs: string[];
};

function pretty(value: unknown) {
  if (value === null || value === undefined) return "";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function EtlComparePage() {
  const [filters, setFilters] = useState({
    lotId: "",
    sourceId: "",
    entite: "",
    refExterne: "",
    changedOnly: true
  });
  const optionsQuery = useQuery({
    queryKey: ["/api/admin/etl/compare/options", filters.lotId, filters.sourceId, filters.entite, filters.refExterne],
    queryFn: () => apiRequest<CompareOptions>("/api/admin/etl/compare/options", { query: filters })
  });
  const listQuery = useQuery({
    queryKey: ["/api/admin/etl/compare/changes", filters],
    queryFn: () => apiRequest<EtlCompareChange[]>("/api/admin/etl/compare/changes", { query: { ...filters, page: 1, pageSize: 20 } })
  });

  const controlsColumns: Column<ControleQualite>[] = [
    { key: "regle", header: "Regle", render: (row) => row.code_controle || "—" },
    { key: "champ", header: "Champ", render: (row) => row.nom_champ || "—" },
    { key: "niveau", header: "Niveau", render: (row) => <StatusBadge value={row.niveau} /> },
    { key: "decision", header: "Decision", render: (row) => row.decision_finale || "—" },
    { key: "obs", header: "Valeur observee", render: (row) => row.valeur_observee || "—" },
    { key: "corr", header: "Valeur corrigee", render: (row) => row.valeur_corrigee || "—" }
  ];

  const flows = listQuery.data || [];
  const cards = useMemo(() => flows.map((flow, index) => (
    <ChartCard
      key={`${flow.lot.id}-${flow.entite}-${flow.ref_externe || index}`}
      title={`${flow.source.nom} -> ${flow.entite}`}
      subtitle={`Lot ${flow.lot.nom} • Ref ${flow.ref_externe || "sans ref"} • ${flow.has_changes ? "modifie" : "normalise"}`}
      expandable
      data={[
        { source: flow.source.nom, lot: flow.lot.nom, entite: flow.entite, ref_externe: flow.ref_externe || "—", has_changes: flow.has_changes },
        ...flow.quality_controls.map((control) => ({
          niveau: control.niveau || "—",
          decision: control.decision_finale || "—",
          code: control.code_controle || "—",
          description: control.description || "—"
        }))
      ]}
    >
      <div className="pipeline">
        <span>Source</span><span>Enregistrement brut</span><span>Staging normalise</span><span>Controle qualite</span><span>Tables metier</span>
      </div>
      <div className="compare-grid">
        <div className="chart-card">
          <div className="chart-card-header"><div><h2>Donnee brute</h2></div></div>
          {flow.raw ? <pre className="json-pre">{pretty(flow.raw.payload_json)}</pre> : <div className="muted">Donnee brute correspondante non trouvee.</div>}
        </div>
        <div className="etl-arrow">
          <div className="etl-arrow-visual">
            <div>Transformation ETL</div>
            <div className="etl-arrow-line" />
          </div>
        </div>
        <div className="chart-card">
          <div className="chart-card-header"><div><h2>Staging normalise</h2></div></div>
          <div className="muted" style={{ marginBottom: 8 }}>
            Parseable : <StatusBadge value={flow.staging?.est_parseable === false ? "KO" : "OK"} />
            {" • "}Validation : {flow.staging?.statut_validation || "—"}
            {flow.staging?.code_rejet_potentiel ? ` • Code rejet : ${flow.staging.code_rejet_potentiel}` : ""}
          </div>
          {flow.staging ? <pre className="json-pre">{pretty(flow.staging.payload_normalise_json)}</pre> : <div className="muted">Aucune donnee staging disponible.</div>}
        </div>
      </div>
      <div className="chart-card">
        <div className="chart-card-header"><div><h2>Controles qualite lies</h2></div></div>
        <DataTable rows={flow.quality_controls} columns={controlsColumns} getRowKey={(row) => row.controle_id} emptyLabel="Aucun controle associe." />
      </div>
    </ChartCard>
  )), [flows]);

  return (
    <Page title="Avant / Apres ETL" eyebrow="Demonstration ETL">
      <ChartCard title="Filtres">
        <div className="filter-bar">
          <Field label="Lot">
            <Select value={filters.lotId} onChange={(event) => setFilters((prev) => ({ ...prev, lotId: event.target.value }))}>
              <option value="">Tous les lots</option>
              {(optionsQuery.data?.lots || []).map((lot) => <option key={lot.id} value={lot.id}>{lot.nom}</option>)}
            </Select>
          </Field>
          <Field label="Source">
            <Select value={filters.sourceId} onChange={(event) => setFilters((prev) => ({ ...prev, sourceId: event.target.value }))}>
              <option value="">Toutes les sources</option>
              {(optionsQuery.data?.sources || []).map((source) => <option key={source.id} value={source.id}>{source.nom}</option>)}
            </Select>
          </Field>
          <Field label="Entite">
            <Select value={filters.entite} onChange={(event) => setFilters((prev) => ({ ...prev, entite: event.target.value }))}>
              <option value="">Toutes les entites</option>
              {(optionsQuery.data?.entites || []).map((item) => <option key={item} value={item}>{item}</option>)}
            </Select>
          </Field>
          <Field label="Ref externe">
            <Input value={filters.refExterne} onChange={(event) => setFilters((prev) => ({ ...prev, refExterne: event.target.value }))} placeholder="Filtrer une ref" />
          </Field>
          <label className="field">
            <span>Affichage</span>
            <Button variant={filters.changedOnly ? "primary" : "secondary"} onClick={() => setFilters((prev) => ({ ...prev, changedOnly: !prev.changedOnly }))}>
              {filters.changedOnly ? "Seulement modifiees" : "Toutes les donnees"}
            </Button>
          </label>
          <Button variant="secondary" onClick={() => setFilters({ lotId: "", sourceId: "", entite: "", refExterne: "", changedOnly: true })}>
            <RotateCcw size={16} />
            Reset
          </Button>
        </div>
      </ChartCard>

      {listQuery.isLoading ? <LoadingState label="Chargement des flux ETL..." /> : null}
      {listQuery.isError ? <ErrorState message={listQuery.error.message} onRetry={() => listQuery.refetch()} /> : null}
      {!listQuery.isLoading && !listQuery.isError && cards.length === 0 ? <div className="state">Aucun flux ETL pour ces filtres.</div> : null}
      {cards}
    </Page>
  );
}
