"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { RotateCcw, ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";
import { BarSeries } from "@/src/components/charts/BarSeries";
import { LineSeries } from "@/src/components/charts/LineSeries";
import { PieSeries } from "@/src/components/charts/PieSeries";
import { StatusBadge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { ChartCard, MetricCard } from "@/src/components/ui/cards";
import type { Column } from "@/src/components/ui/data-table";
import { Input, Select } from "@/src/components/ui/forms";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { apiRequest } from "@/src/lib/api";
import { compactDate, formatNumber } from "@/src/lib/format";
import type { AdminQualityKpis, ControleQualite, QualityFilterOptions } from "@/src/types/domain";
import { CrudList, Page } from "./_shared";

function useChart<T>(path: string, params: Record<string, string>) {
  return useQuery({
    queryKey: [path, params],
    queryFn: () => apiRequest<T>(path, { query: params })
  });
}

export function QualitePage() {
  const [filters, setFilters] = useState({
    niveau: "",
    decision: "",
    entite: "",
    sourceId: "",
    lotId: ""
  });

  const params = useMemo(() => {
    const p: Record<string, string> = {};
    if (filters.niveau) p.niveau = filters.niveau;
    if (filters.decision) p.decision = filters.decision;
    if (filters.entite) p.entite = filters.entite;
    if (filters.sourceId) p.sourceId = filters.sourceId;
    if (filters.lotId) p.lotId = filters.lotId;
    return p;
  }, [filters]);

  const options = useQuery({
    queryKey: ["/api/admin/qualite/filters"],
    queryFn: () => apiRequest<QualityFilterOptions>("/api/admin/qualite/filters")
  });
  const kpis = useChart<AdminQualityKpis>("/api/admin/qualite/kpis", params);
  const levels = useChart<{ niveau: string; nb: number }[]>("/api/admin/qualite/charts/levels", params);
  const decisions = useChart<{ decision_finale: string; nb: number }[]>("/api/admin/qualite/charts/decisions", params);
  const topRules = useChart<{ regle_id: number; code_regle: string; severite: string; nb: number }[]>("/api/admin/qualite/charts/top-rules", params);
  const topFields = useChart<{ nom_champ: string; nb: number }[]>("/api/admin/qualite/charts/top-fields", params);
  const bySource = useChart<{ source_id: number; nom: string; nb: number }[]>("/api/admin/qualite/charts/by-source", params);
  const byLot = useChart<{ lot_id: number; nom_lot: string; nb: number }[]>("/api/admin/qualite/charts/by-lot", params);
  const timeline = useChart<{ bucket: string; nb: number }[]>("/api/admin/qualite/charts/timeline", { ...params, granularity: "day" });
  const list = usePagedApi<ControleQualite>("/api/admin/qualite/controles", params);
  const rows = list.data?.data || [];

  const columns: Column<ControleQualite>[] = [
    { key: "id", header: "ID", render: (row) => row.controle_id, align: "right" },
    { key: "entity", header: "Entite", render: (row) => row.entite },
    { key: "field", header: "Champ", render: (row) => row.nom_champ || "N/A" },
    { key: "level", header: "Niveau", render: (row) => <StatusBadge value={row.niveau} /> },
    { key: "blocking", header: "Bloquant", render: (row) => <StatusBadge value={row.est_bloquant} /> },
    { key: "decision", header: "Decision", render: (row) => row.decision_finale || "N/A" },
    { key: "desc", header: "Description", render: (row) => row.description || row.code_controle || "N/A" }
  ];

  const timelineData = (timeline.data || []).map((row) => ({ ...row, label: compactDate(row.bucket) }));
  const noResults = !list.isLoading && rows.length === 0;

  return (
    <Page title="Controles qualite" eyebrow="Gouvernance">
      <div className="metric-grid">
        <MetricCard label="Total controles" value={formatNumber(kpis.data?.nb_total)} icon={ShieldCheck} />
        <MetricCard label="Bloquants" value={formatNumber(kpis.data?.nb_bloquants)} icon={ShieldAlert} />
        <MetricCard label="Rejets" value={formatNumber(kpis.data?.nb_rejets)} icon={ShieldX} />
        <MetricCard label="Ratio bloquants" value={formatNumber((kpis.data?.ratio_bloquants ?? 0) * 100, " %")} icon={ShieldAlert} />
        <MetricCard label="Ratio rejets" value={formatNumber((kpis.data?.ratio_rejets ?? 0) * 100, " %")} icon={ShieldX} />
        <MetricCard label="Entites distinctes" value={formatNumber(kpis.data?.nb_entites_distinctes)} icon={ShieldCheck} />
      </div>

      <div className="filter-bar">
        <Select value={filters.niveau} onChange={(event) => setFilters((prev) => ({ ...prev, niveau: event.target.value }))}>
          <option value="">Niveau: tous</option>
          {(options.data?.niveaux || []).map((value) => <option key={value} value={value}>{value}</option>)}
        </Select>
        <Select value={filters.decision} onChange={(event) => setFilters((prev) => ({ ...prev, decision: event.target.value }))}>
          <option value="">Decision: toutes</option>
          {(options.data?.decisions || []).map((value) => <option key={value} value={value}>{value}</option>)}
        </Select>
        <Select value={filters.entite} onChange={(event) => setFilters((prev) => ({ ...prev, entite: event.target.value }))}>
          <option value="">Entite: toutes</option>
          {(options.data?.entites || []).map((value) => <option key={value} value={value}>{value}</option>)}
        </Select>
        <Select value={filters.sourceId} onChange={(event) => setFilters((prev) => ({ ...prev, sourceId: event.target.value }))}>
          <option value="">Source: toutes</option>
          {(options.data?.sources || []).map((source) => <option key={source.id} value={source.id}>{source.nom}</option>)}
        </Select>
        <Select value={filters.lotId} onChange={(event) => setFilters((prev) => ({ ...prev, lotId: event.target.value }))}>
          <option value="">Lot: tous</option>
          {(options.data?.lots || []).map((lot) => <option key={lot.id} value={lot.id}>{lot.nom}</option>)}
        </Select>
        <Button variant="secondary" onClick={() => setFilters({ niveau: "", decision: "", entite: "", sourceId: "", lotId: "" })}>
          <RotateCcw size={16} />
          Reinitialiser les filtres
        </Button>
      </div>

      {noResults ? <div className="state">Aucun controle pour ces filtres.</div> : null}

      <div className="chart-grid">
        <ChartCard title="Repartition par niveau" expandable data={levels.data || []} empty={!levels.data?.length}>
          <PieSeries data={levels.data || []} dataKey="nb" nameKey="niveau" />
        </ChartCard>
        <ChartCard title="Repartition par decision" expandable data={decisions.data || []} empty={!decisions.data?.length}>
          <PieSeries data={decisions.data || []} dataKey="nb" nameKey="decision_finale" />
        </ChartCard>
      </div>

      <div className="chart-grid">
        <ChartCard title="Top regles" subtitle="Occurrences les plus frequentes" expandable data={topRules.data || []} empty={!topRules.data?.length}>
          <BarSeries data={topRules.data || []} xKey="code_regle" series={[{ key: "nb", label: "Occurrences", color: "#2563eb" }]} />
        </ChartCard>
        <ChartCard title="Top champs" subtitle="Champs les plus controles" expandable data={topFields.data || []} empty={!topFields.data?.length}>
          <BarSeries data={topFields.data || []} xKey="nom_champ" series={[{ key: "nb", label: "Occurrences", color: "#b54708" }]} />
        </ChartCard>
      </div>

      <div className="chart-grid">
        <ChartCard title="Par source" expandable data={bySource.data || []} empty={!bySource.data?.length}>
          <BarSeries data={bySource.data || []} xKey="nom" series={[{ key: "nb", label: "Controles", color: "#0284c7" }]} />
        </ChartCard>
        <ChartCard title="Par lot" expandable data={byLot.data || []} empty={!byLot.data?.length}>
          <BarSeries data={byLot.data || []} xKey="nom_lot" series={[{ key: "nb", label: "Controles", color: "#dc2626" }]} />
        </ChartCard>
      </div>

      <ChartCard title="Timeline (jour)" subtitle="Evolution des controles sur la periode" expandable data={timelineData} empty={!timelineData.length}>
        <LineSeries data={timelineData} xKey="label" series={[{ key: "nb", label: "Controles", color: "#dc2626" }]} />
      </ChartCard>

      <CrudList
        query={list}
        rows={rows}
        columns={columns}
        getRowKey={(row) => row.controle_id}
        emptyLabel="Aucun controle pour ces filtres."
      />
    </Page>
  );
}
