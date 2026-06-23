"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Activity, ChevronRight, Flame, Plus } from "lucide-react";
import { BarSeries } from "@/src/components/charts/BarSeries";
import { LineSeries } from "@/src/components/charts/LineSeries";
import { Button } from "@/src/components/ui/button";
import { ChartCard, MetricCard } from "@/src/components/ui/cards";
import { DataTable, type Column } from "@/src/components/ui/data-table";
import { Input, Select } from "@/src/components/ui/forms";
import { Pagination } from "@/src/components/ui/pagination";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { useSeancesFilters } from "@/src/features/seances/hooks";
import { apiRequest } from "@/src/lib/api";
import { SEANCE_FIELDS } from "@/src/lib/payload";
import { compactDate, formatDate, formatNumber } from "@/src/lib/format";
import type { Seance } from "@/src/types/domain";
import { AddEntryModal, Page } from "./_shared";

type SeanceChartPoint = { bucket: string; value?: number | null; count?: number; nb?: number; calories?: number };
type SeancesChart = { points: SeanceChartPoint[]; granularity?: string };

export function SeancesPage() {
  const router = useRouter();
  const [type, setType] = useState("");
  const [niveau, setNiveau] = useState("");
  const [minKcal, setMinKcal] = useState("");
  const [adding, setAdding] = useState(false);
  const query = usePagedApi<Seance>("/api/me/seances", {}, 12);
  const filters = useSeancesFilters();

  const charts = useQuery({
    queryKey: ["/api/me/seances/charts", "week"],
    queryFn: () =>
      apiRequest<SeancesChart>("/api/me/seances/charts", { query: { granularity: "week" } })
  });
  const caloriesChart = useQuery({
    queryKey: ["/api/me/seances/charts", "calories", "day"],
    queryFn: () =>
      apiRequest<SeancesChart>("/api/me/seances/charts", {
        query: { granularity: "day", metric: "calories_brulees_total" }
      })
  });

  const allRows = query.data?.data || [];
  const rows = useMemo(
    () =>
      allRows.filter((row) => {
        if (type && (row.type_entrainement || "") !== type) return false;
        if (niveau && (row.niveau_experience || "") !== niveau) return false;
        if (minKcal && (row.calories_brulees_total ?? 0) < Number(minKcal)) return false;
        return true;
      }),
    [allRows, type, niveau, minKcal]
  );

  const columns: Column<Seance>[] = [
    {
      key: "date",
      header: "Date",
      render: (row) => formatDate(row.date_seance)
    },
    { key: "type", header: "Type", render: (row) => row.type_entrainement || "N/A" },
    { key: "duree", header: "Duree", render: (row) => formatNumber(row.duree_seance_min, " min"), align: "right" },
    { key: "calories", header: "Calories", render: (row) => formatNumber(row.calories_brulees_total, " kcal"), align: "right" },
    { key: "niveau", header: "Niveau", render: (row) => row.niveau_experience || "N/A" },
    {
      key: "voir",
      header: "",
      align: "right",
      render: () => <span className="row-open-hint">Voir detail <ChevronRight size={14} /></span>
    }
  ];

  const totalDuree = rows.reduce((sum, row) => sum + (row.duree_seance_min || 0), 0);
  const totalKcal = rows.reduce((sum, row) => sum + (row.calories_brulees_total || 0), 0);

  const summary = (
    <div className="metric-grid compact">
      <MetricCard label="Duree page courante" value={formatNumber(totalDuree, " min")} icon={Activity} />
      <MetricCard label="Calories page courante" value={formatNumber(totalKcal, " kcal")} icon={Flame} />
    </div>
  );

  const sessionsPerWeek = (charts.data?.points || []).map((p) => ({
    label: compactDate(p.bucket),
    nb: p.nb ?? p.count ?? 0
  }));
  const burnedKcal = (caloriesChart.data?.points || []).map((p) => ({
    label: compactDate(p.bucket),
    kcal: p.calories ?? p.value ?? 0
  }));

  const chartsBlock = (
    <div className="chart-grid">
      <ChartCard title="Seances par semaine" expandable data={sessionsPerWeek}>
        <BarSeries data={sessionsPerWeek} xKey="label" series={[{ key: "nb", label: "Seances", color: "#2563eb" }]} />
      </ChartCard>
      <ChartCard title="Calories brulees par jour" expandable data={burnedKcal}>
        <LineSeries data={burnedKcal} xKey="label" series={[{ key: "kcal", label: "Calories", color: "#dc2626" }]} />
      </ChartCard>
    </div>
  );

  const filterBar = (
    <div className="filter-bar">
      <Select value={type} onChange={(event) => setType(event.target.value)} disabled={filters.isLoading}>
        <option value="">
          {filters.isLoading ? "Chargement..." : "Tous les types"}
        </option>
        {filters.data?.types_entrainement && filters.data.types_entrainement.length > 0 ? (
          filters.data.types_entrainement.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))
        ) : null}
      </Select>
      <Select value={niveau} onChange={(event) => setNiveau(event.target.value)} disabled={filters.isLoading}>
        <option value="">
          {filters.isLoading ? "Chargement..." : "Tous les niveaux"}
        </option>
        {filters.data?.niveaux_experience && filters.data.niveaux_experience.length > 0 ? (
          filters.data.niveaux_experience.map((n) => (
            <option key={n} value={n}>{n}</option>
          ))
        ) : null}
      </Select>
      <Input
        type="number"
        min={0}
        placeholder="Calories minimum"
        value={minKcal}
        onChange={(event) => setMinKcal(event.target.value)}
      />
    </div>
  );

  return (
    <>
      <Page
        title="Historique des seances"
        eyebrow="Entrainement"
        actions={<Button onClick={() => setAdding(true)}><Plus size={16} /> Nouvelle seance</Button>}
      >
        {filterBar}
        {summary}
        {chartsBlock}
        {query.isLoading ? <LoadingState /> : null}
        {query.isError ? <ErrorState message={query.error.message} onRetry={() => query.refetch()} /> : null}
        {!query.isLoading && !query.isError ? (
          <>
            <DataTable
              rows={rows}
              columns={columns}
              getRowKey={(row) => row.seance_id}
              onRowClick={(row) => router.push(`/me/seances/${row.seance_id}`)}
            />
            <Pagination meta={query.data?.meta} page={query.page} onPageChange={query.setPage} />
          </>
        ) : null}
      </Page>
      <AddEntryModal
        open={adding}
        onClose={() => setAdding(false)}
        title="Nouvelle seance"
        path="/api/me/seances"
        invalidateKey="/api/me/seances"
        cleanOptions={SEANCE_FIELDS}
        initialValues={{ date_seance: new Date().toISOString().slice(0, 16) }}
        fields={[
          { name: "date_seance", label: "Date", type: "datetime-local", required: true },
          { name: "type_entrainement", label: "Type", options: [
            { label: "Musculation", value: "MUSCULATION" },
            { label: "Cardio", value: "CARDIO" },
            { label: "Mobilite", value: "MOBILITE" },
            { label: "HIIT", value: "HIIT" }
          ] },
          { name: "duree_seance_min", label: "Duree (min)", type: "number" },
          { name: "calories_brulees_total", label: "Calories", type: "number", step: "0.1" },
          { name: "frequence_entrainement_j_sem", label: "Freq. /sem", type: "number" },
          { name: "niveau_experience", label: "Niveau", options: [
            { label: "Debutant", value: "DEBUTANT" },
            { label: "Intermediaire", value: "INTERMEDIAIRE" },
            { label: "Avance", value: "AVANCE" }
          ] },
          { name: "eau_l", label: "Eau (L)", type: "number", step: "0.1" }
        ]}
      />
    </>
  );
}
