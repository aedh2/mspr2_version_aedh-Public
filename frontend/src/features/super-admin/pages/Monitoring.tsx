"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { BarSeries } from "@/src/components/charts/BarSeries";
import { StatusBadge } from "@/src/components/ui/badge";
import { ChartCard, MetricCard } from "@/src/components/ui/cards";
import { DataTable, type Column } from "@/src/components/ui/data-table";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { apiRequest } from "@/src/lib/api";
import { formatDate, formatNumber } from "@/src/lib/format";
import type { BlockedLot, FailedExecution } from "@/src/types/domain";
import { Page } from "@/src/features/admin/pages/_shared";

type RecentLot = {
  lot_id: number;
  nom_lot?: string | null;
  statut?: string | null;
  cree_le?: string | null;
  execution_id?: number | null;
  source_id?: number | null;
  nb_bloquants?: number | null;
};

type MonitoringEtl = {
  kpis?: Record<string, number>;
  executions_echec: FailedExecution[];
  lots_bloques: BlockedLot[];
  executions_recentes?: FailedExecution[];
  lots_recents?: RecentLot[];
  executions_par_statut?: Array<{ name: string; value: number }>;
};

type MonitoringQualite = {
  qualite_par_source: Array<{ name: string; value: number }>;
  volumes_par_source: Array<{ nom: string; lignes_lues: number; lignes_valides: number; lignes_invalides: number; nb_rejets: number }>;
  rejet_par_source?: Array<{ name: string; value: number }>;
  lots_anomalies?: Array<{ name: string; value: number }>;
  lots_avec_anomalies?: Array<{ name: string; value: number }>;
};

export function SuperAdminMonitoringPage() {
  const router = useRouter();
  const etl = useQuery({ queryKey: ["/api/super-admin/monitoring/etl"], queryFn: () => apiRequest<MonitoringEtl>("/api/super-admin/monitoring/etl") });
  const qualite = useQuery({ queryKey: ["/api/super-admin/monitoring/qualite"], queryFn: () => apiRequest<MonitoringQualite>("/api/super-admin/monitoring/qualite") });

  if (etl.isLoading || qualite.isLoading) return <LoadingState />;
  if (etl.isError) return <ErrorState message={etl.error.message} onRetry={() => etl.refetch()} />;
  if (qualite.isError) return <ErrorState message={qualite.error.message} onRetry={() => qualite.refetch()} />;

  const failed = etl.data?.executions_echec || [];
  const recentExecutions = etl.data?.executions_recentes || [];
  const blocked = etl.data?.lots_bloques || [];
  const recentLots = etl.data?.lots_recents || [];
  const volumes = qualite.data?.volumes_par_source || [];
  const kpis = etl.data?.kpis || {};
  const anomalyLots = qualite.data?.lots_avec_anomalies || qualite.data?.lots_anomalies || [];
  const rejectRate = qualite.data?.rejet_par_source || volumes.map((row) => ({
    name: row.nom,
    value: row.lignes_lues ? (row.nb_rejets / row.lignes_lues) * 100 : 0
  }));

  const executionColumns: Column<FailedExecution>[] = [
    { key: "id", header: "ID", align: "right", render: (row) => row.execution_id },
    { key: "statut", header: "Statut", render: (row) => <StatusBadge value={row.statut} /> },
    { key: "qualite", header: "Qualite", render: (row) => formatNumber(row.taux_qualite, " %"), align: "right" },
    { key: "rejets", header: "Rejets", render: (row) => formatNumber(row.nb_rejets), align: "right" },
    { key: "termine", header: "Termine le", render: (row) => formatDate(row.termine_le) },
    { key: "msg", header: "Message", render: (row) => row.message || "N/A" }
  ];

  const blockedColumns: Column<BlockedLot | RecentLot>[] = [
    { key: "id", header: "ID", align: "right", render: (row) => row.lot_id },
    { key: "nom", header: "Nom lot", render: (row) => row.nom_lot || "N/A" },
    { key: "statut", header: "Statut", render: (row) => <StatusBadge value={row.statut} /> },
    { key: "bloquants", header: "Bloquants", render: (row) => formatNumber((row as BlockedLot).nb_bloquants), align: "right" },
    { key: "cree", header: "Cree le", render: (row) => formatDate(row.cree_le) }
  ];

  return (
    <Page title="Monitoring" eyebrow="Super administration">
      <div className="metric-grid">
        <MetricCard label="Executions" value={formatNumber(kpis.total_executions)} />
        <MetricCard label="Succes" value={formatNumber(kpis.executions_succes)} />
        <MetricCard label="Echecs" value={formatNumber(kpis.executions_echec)} />
        <MetricCard label="Lots bloques" value={formatNumber(kpis.lots_bloques)} />
        <MetricCard label="Qualite moyenne" value={formatNumber(kpis.taux_qualite_moyen, " %")} />
        <MetricCard label="Taux rejet global" value={formatNumber(kpis.taux_rejet_global, " %")} />
      </div>

      <div className="chart-grid">
        <ChartCard title="Executions par statut" expandable data={etl.data?.executions_par_statut || []} empty={!etl.data?.executions_par_statut?.length}>
          <BarSeries data={etl.data?.executions_par_statut || []} xKey="name" series={[{ key: "value", label: "Executions", color: "#2563eb" }]} />
        </ChartCard>
        <ChartCard title="Qualite par source" expandable data={qualite.data?.qualite_par_source || []} empty={!qualite.data?.qualite_par_source?.length}>
          <BarSeries data={qualite.data?.qualite_par_source || []} xKey="name" series={[{ key: "value", label: "Qualite (%)", color: "#0284c7" }]} />
        </ChartCard>
        <ChartCard title="Volumes par source" expandable data={volumes} empty={!volumes.length}>
          <BarSeries data={volumes} xKey="nom" series={[
            { key: "lignes_lues", label: "Lues", color: "#2563eb" },
            { key: "lignes_valides", label: "Valides", color: "#0284c7" },
            { key: "lignes_invalides", label: "Invalides", color: "#b54708" },
          ]} />
        </ChartCard>
        <ChartCard title="Lots avec anomalies" expandable data={anomalyLots} empty={!anomalyLots.length}>
          <BarSeries data={anomalyLots} xKey="name" series={[{ key: "value", label: "Controles", color: "#dc2626" }]} />
        </ChartCard>
      </div>

      <ChartCard title="Taux de rejet par source (%)" expandable data={rejectRate} empty={!rejectRate.length}>
        <BarSeries data={rejectRate} xKey="name" series={[{ key: "value", label: "Taux de rejet (%)", color: "#dc2626" }]} />
      </ChartCard>

      <section className="page-section">
        <h2>Executions en echec</h2>
        {failed.length ? (
          <DataTable rows={failed} columns={executionColumns} getRowKey={(row) => row.execution_id} onRowClick={(row) => router.push(`/admin/etl/executions/${row.execution_id}`)} />
        ) : (
          <>
            <div className="state">Aucune execution en echec — tous les pipelines sont OK.</div>
            <DataTable rows={recentExecutions} columns={executionColumns} getRowKey={(row) => row.execution_id} onRowClick={(row) => router.push(`/admin/etl/executions/${row.execution_id}`)} emptyLabel="Aucune execution recente." />
          </>
        )}
      </section>

      <section className="page-section">
        <h2>Lots bloques</h2>
        {blocked.length ? (
          <DataTable rows={blocked} columns={blockedColumns} getRowKey={(row) => row.lot_id} onRowClick={(row) => router.push(`/admin/etl/lots/${row.lot_id}`)} />
        ) : (
          <>
            <div className="state">Aucun lot bloque — workflow fluide.</div>
            <DataTable rows={recentLots} columns={blockedColumns} getRowKey={(row) => row.lot_id} onRowClick={(row) => router.push(`/admin/etl/lots/${row.lot_id}`)} emptyLabel="Aucun lot recent." />
          </>
        )}
      </section>
    </Page>
  );
}
