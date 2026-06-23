"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, DatabaseZap, ShieldAlert, Users } from "lucide-react";
import { BarSeries } from "@/src/components/charts/BarSeries";
import { ChartCard, MetricCard } from "@/src/components/ui/cards";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { apiRequest } from "@/src/lib/api";
import { formatNumber } from "@/src/lib/format";
import type { SuperAdminDashboard } from "@/src/types/domain";
import { Page } from "@/src/features/admin/pages/_shared";

type QualityByOrg = { organisation_id: number; nom: string; qualite_moy: number | null; nb_executions: number };
type VolumesBySource = { source_id: number; nom: string; lignes_lues: number; lignes_valides: number; lignes_invalides?: number; nb_rejets: number };

function useChart<T>(path: string) {
  return useQuery({
    queryKey: [path],
    queryFn: () => apiRequest<T>(path)
  });
}

function GlobalHeatmap({ data }: { data: QualityByOrg[] }) {
  if (!data.length) return <p className="muted">Aucune donnee.</p>;
  const max = Math.max(...data.map((row) => row.nb_executions || 0), 1);
  return (
    <div className="heatmap-grid">
      {data.map((row) => {
        const quality = row.qualite_moy ?? 0;
        const intensity = Math.min(1, (row.nb_executions || 0) / max);
        const hue = Math.round(120 * (quality / 100));
        const background = `hsla(${hue}, 70%, 45%, ${0.25 + 0.6 * intensity})`;
        return (
          <div key={row.organisation_id} className="heatmap-cell" style={{ background }}>
            <strong>{row.nom}</strong>
            <span>{formatNumber(quality, " %")}</span>
            <small>{row.nb_executions} exe.</small>
          </div>
        );
      })}
    </div>
  );
}

export function SuperAdminDashboardPage() {
  const dashboard = useQuery({
    queryKey: ["super-admin-dashboard"],
    queryFn: () => apiRequest<SuperAdminDashboard>("/api/super-admin/dashboard")
  });
  const qualityByOrg = useChart<QualityByOrg[]>("/api/super-admin/dashboard/charts/quality-by-organisation");
  const volumesBySource = useChart<VolumesBySource[]>("/api/super-admin/dashboard/charts/volumes-by-source");

  if (dashboard.isLoading) return <LoadingState />;
  if (dashboard.isError) return <ErrorState message={dashboard.error.message} onRetry={() => dashboard.refetch()} />;
  const data = dashboard.data;

  return (
    <Page title="Dashboard global" eyebrow="Super administration" subtitle="Vue globale des organisations, volumes ETL et indicateurs de qualite.">
      <div className="metric-grid">
        <MetricCard label="Utilisateurs" value={formatNumber(data?.nb_utilisateurs)} icon={Users} />
        <MetricCard label="Admins" value={formatNumber(data?.nb_admins)} icon={Building2} />
        <MetricCard label="Executions ETL" value={formatNumber(data?.nb_executions_etl)} icon={DatabaseZap} />
        <MetricCard label="Qualite min" value={formatNumber(data?.qualite_min, " %")} icon={ShieldAlert} />
        <MetricCard label="Qualite max" value={formatNumber(data?.qualite_max, " %")} icon={ShieldAlert} />
      </div>

      <div className="chart-grid">
        <ChartCard title="Qualite moyenne par organisation" expandable data={(qualityByOrg.data || []).map((row) => ({ ...row, qualite: row.qualite_moy ?? 0 }))} empty={!qualityByOrg.data?.length}>
          <BarSeries
            data={(qualityByOrg.data || []).map((row) => ({ ...row, qualite: row.qualite_moy ?? 0 }))}
            xKey="nom"
            series={[{ key: "qualite", label: "Qualite (%)", color: "#0284c7" }]}
          />
        </ChartCard>
        <ChartCard title="Volumes par source" expandable data={volumesBySource.data || []} empty={!volumesBySource.data?.length}>
          <BarSeries
            data={volumesBySource.data || []}
            xKey="nom"
            series={[
              { key: "lignes_lues", label: "Lues", color: "#2563eb" },
              { key: "lignes_valides", label: "Valides", color: "#0284c7" },
              { key: "lignes_invalides", label: "Invalides", color: "#b54708" },
              { key: "nb_rejets", label: "Rejets", color: "#dc2626" }
            ]}
          />
        </ChartCard>
      </div>

      <ChartCard title="Heatmap qualite x volume (par organisation)" expandable={false}>
        <GlobalHeatmap data={qualityByOrg.data || []} />
      </ChartCard>
    </Page>
  );
}
